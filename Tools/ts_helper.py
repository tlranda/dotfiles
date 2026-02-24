# Dependent libraries
import pandas as pd
# Why no PyExifTool? It does not re-implement ExifTool and STILL requires your install
# Otherwise, it's over-engineered compared to current support plans.
# Ideally, we strip Pandas out later, but I'm willing to accept the overhead as
# it is easy to request and actually provides a lot of value that is harder to
# replicate separately

# Builtin libraries  -- no extra installations required
import argparse
from collections import defaultdict
import datetime
from io import StringIO
import os
import pathlib
import sqlite3
import subprocess
from typing import Callable, Dict, List, Optional, Tuple, Union
import warnings

"""
    Pandas Management Assistance
"""

def pandas_append_series_to_end_of_frame(df: pd.DataFrame,
                                         se: pd.Series,
                                         ) -> pd.DataFrame:
    """
        There's probably a better way to do this, but this pattern shows up a lot
        and it is ugly AF
    """
    return pd.concat((df,
                      pd.DataFrame(se).T.set_index([pd.Index([len(df)])]),
                      ))

"""
    SQLite3 Management Assistance
"""

def get_db_connection(fname: Union[pathlib.Path, str],
                      with_con: bool = False,
                      ) -> Union[sqlite3.Cursor,
                                  Tuple[sqlite3.Cursor, sqlite3.Connection]]:
    # SQLite helper to initiate db connection
    con = sqlite3.connect(fname)
    if with_con:
        return con.cursor(), con
    return con.cursor()

def get_tables(cur: sqlite3.Cursor,
               ) -> pd.DataFrame:
    # SQLite helper: Fetch all of the tables from given cursor's main schema

    # Expect columns based on SQLite version 3.37.0 (2021/11/27) documentation
    # More columns may be added in the future
    expect_columns = ['schema','name','type','ncol','wr','strict']
    cur.execute('PRAGMA main.table_list;')
    records = cur.fetchall()
    return pd.DataFrame.from_records(records, columns=expect_columns)

def get_table_description(cur: sqlite3.Cursor,
                          name: str,
                          ) -> pd.DataFrame:
    # SQLite helper: Fetch table schema for main schema's table of given name

    expect_columns = ['index','name','type','notnull','default_value','pk']
    cur.execute(f'PRAGMA main.table_info({name});')
    records = cur.fetchall()
    return pd.DataFrame.from_records(records, columns=expect_columns)

def get_table_data(cur: sqlite3.Cursor,
                   name: str,
                   table_descriptions: Optional[Dict[str, pd.DataFrame]] = None,
                   ) -> pd.DataFrame:
    # SQLite helper: Format all data from table name as Pandas DF

    # Schema retrieval for column naming
    if table_descriptions is None:
        table_descriptions = {
                name: get_table_description(cur, name)
                }
    expect_columns = list(table_descriptions[name]['name'])

    cur.execute(f'SELECT * FROM {name};')
    results = cur.fetchall()
    return pd.DataFrame.from_records(results, columns=expect_columns)

def sqlite_db_load(dbname: Union[str, pathlib.Path],
                   ) -> Tuple[sqlite3.Cursor, Dict[str, pd.DataFrame]]:
    # Load all SQLite data from a database with possible hash-updates prior to return

    cur = get_db_connection(dbname)
    avail_tables = get_tables(cur)
    all_table_data = dict()
    # Pandas does not support retrieving the sqlite_schema, but we do not need it
    skip_names = ['sqlite_schema']
    for table_name in avail_tables['name']:
        if table_name in skip_names:
            continue
        # Pandas only supports URIs for now; cannot reuse sqlite cursor/connection
        all_table_data[table_name] = pd.read_sql_table(table_name,
                                                       f"sqlite:///{dbname}")

    # ALTERNATIVE: Reuse the SQLite cursor (and can read sqlite_schema table)
    #all_table_data = dict()
    #for table_name in avail_tables['name']:
    #    if table_name in skip_names:
    #        continue
    #    all_table_data[table_name] = get_table_data(cur, table_name)

    return cur, all_table_data

def sqlite_db_save(dbname: str,
                   dbdatadict: Dict[str, pd.DataFrame],
                   ) -> None:
    # Save mapped dataframes to given database name as a single SQLite DB

    # Implicitly creates db if not exists
    cur, con = get_db_connection(dbname, with_con=True)
    # CANNOT REPLACE this database
    PROTECTED_TABLES = ['sqlite_sequence']
    for tblname, tbldata in dbdatadict.items():
        if tblname in PROTECTED_TABLES:
            continue
        tbldata.to_sql(tblname, con, if_exists='replace',
                       index=False, method='multi')

"""
--TAGSTUDIO'S SQLITE LAYOUT--

folders: id, path, uuid
entries: folder_id, path, filename, suffix, date_created, date_modified, date_added[, hexdigest]
text_fields: value, id, type_key, entry_id, position
tags: id, name, shorthand, color_namespace, color_slug, is_category, icon, disambiguation_id
tag_entries: tag_id, entry_id
"""

"""
    ExifTool supports TONs of formats, see its documentation for full coverage.
    THIS interface for ExifTool attempts to use the same keys for accessing
    metadata, which may not always be available for all file formats.

    The common metadata keys should work for common formats, including:
        * PNG
        * JPG/JPEG
        * GIF
        * MP3/MP4
    Known to have issues with:
        * WAV
"""
exiftool_mappings = {
    'Artist': ['creator','contributor',],
    'Source': ['source',],
    'URL': ['source',], # NOTE: URL is not always supported (GIF, MP4, etc)
    'Description': ['tags',],
    }

"""
    To play with ExifTool:
    Use -overwrite_original_in_place to prevent file duplication with the _original suffix

    Map-Out:
        Load entries (to know what files go where), maybe folders too
        Load tags to decide what tags should be exported
        Load tag_entries to see mappings that need to be updated
        Load text_fields to see other metadata to export
        Can use Exiftool to mass-update on writeout
        ```
        exiftool -csv="my.csv" PATH
        ```

    Map-In:
        Load entries (to know what files go where), maybe folders too
        For each file, load it in ExifTool and check for its tags etc
            ```
            exiftool -r -csv [-TAGS-TO-LOAD] PATHS > tmp_database.csv
            ```
            Pool all unique tags under a dict (tag: path)
            Also pool other text_fields for import (path: list of fields)
            Both of these ONLY for new/changed values
        Ensure correct values are ready to go, then update sqlite database
"""
def make_exif_dict() -> Dict[str,str]:
    return {'creator': "",
            'contributor': "",
            'source': "",
            'tags': "",
            }

def tagstudio_map_to_csv(csv_path: pathlib.Path,
                         tagstudio_db: dict,
                         ) -> None:
    per_file = dict()
    # Set tag entries to description
    tag_pairs = list(tagstudio_db['tags'][['id','name']].T.to_dict().values())
    tag_mapping = dict()
    for pair in tag_pairs:
        tag_mapping[pair['id']] = pair['name']
    # Set file id to name mapping
    entry_pairs = list(tagstudio_db['entries'][['id','path']].T.to_dict().values())
    entry_mapping = dict()
    for pair in entry_pairs:
        entry_mapping[pair['id']] = pathlib.Path(pair['path'])
    # Mark all tags from tagstudio
    for tag_id, subdf in tagstudio_db['tag_entries'].groupby('tag_id'):
        tag = tag_mapping[tag_id]
        for entry_id in subdf['entry_id']:
            try:
                path = entry_mapping[entry_id]
            except KeyError:
                continue
            if path not in per_file:
                per_file[path] = make_exif_dict()
            proposed_tag = f"{tag};"
            if proposed_tag not in per_file[path]['tags']:
                per_file[path]['tags'] += proposed_tag
    # Mark other fields from tagstudio text fields
    for (field,
        attribution_field,
        joinstr) in zip(['AUTHOR','ARTIST','URL','NOTES'],
                        ['contributor','creator','source','tags'],
                        [', ', ', ','\n','\n']):
        subdf = tagstudio_db['text_fields'][tagstudio_db['text_fields']['type_key'] == field]
        for idx, row in subdf.iterrows():
            try:
                path = entry_mapping[row['entry_id']]
            except KeyError:
                continue
            if path not in per_file:
                per_file[path] = make_exif_dict()
            # Gross way to cleanly append
            per_file[path][attribution_field] = joinstr.join([row['value'],
                                                              per_file[path][attribution_field],
                                                              ]).rstrip().rstrip(joinstr)
    # Now convert each record into a DataFrame for optional disk serialization
    df_cols = ['SourceFile']+sorted(exiftool_mappings.keys())
    fillable = pd.DataFrame(columns=df_cols)
    for (source, attributions) in per_file.items():
        idx = len(fillable)
        new_df = pd.DataFrame(columns=df_cols, index=[idx])
        new_df.loc[idx]['SourceFile'] = source
        for key, map_from in exiftool_mappings.items():
            new_df.loc[idx][key] = attributions[map_from[0]]
            if len(map_from) > 1:
                for extramap in map_from[1:]:
                    if len(attributions[extramap]) > 0:
                        new_df.loc[idx][key] += ", " if len(new_df.loc[idx][key]) > 0 else ""
                        new_df.loc[idx][key] += attributions[extramap]
        fillable = pd.concat((fillable, new_df))
    fillable.to_csv(csv_path, index=False)

def exiftool_map_from_database(csv_path: pathlib.Path,
                               disk_paths: Optional[Union[pathlib.Path, List[pathlib.Path]]],
                               exiftool_path: pathlib.Path,
                               ) -> None:
    if disk_paths is None:
        return
    if not isinstance(disk_paths, list):
        disk_paths = [path]
    # TODO: When this works, consider a flag for adding the overwrite original behavior
    cmd = [exiftool_path, f'-csv={csv_path}']+[f'-{tag}' for tag in exiftool_mappings.keys()]+[str(_) for _ in disk_paths]
    # Batch-call ExifTool on all indicated files
    # This works from command line but not in program
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise ValueError(f"ExifTool return code: {proc.returncode}")

def exiftool_map_from_disk(disk_paths: Optional[Union[pathlib.Path, List[pathlib.Path]]],
                           exiftool_path: pathlib.Path,
                           ) -> Dict[pathlib.Path,Dict[str,str]]:
    lookup = defaultdict(dict)
    if disk_paths is None:
        return lookup
    if not isinstance(disk_paths, list):
        disk_paths = [paths]

    # Batch-call ExifTool on all indicated files
    cmd = [str(exiftool_path), '-r', '-csv', '-Artist', '-Source', '-URL', '-Description']+[str(_) for _ in disk_paths]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise ValueError(f"ExifTool return code: {proc.returncode}")
    output = proc.stdout.decode('utf-8')
    df = pd.read_csv(StringIO(output))
    for idx, row in df.iterrows():
        lookup[pathlib.Path(row['SourceFile'])] = dict((k,v) for (k,v) in row.to_dict().items() if k != 'SourceFile')

    '''
    # Old method for non-CSV inputs
    # Drop empty line and 'X * files read' suffix line (if present)
    output = list(filter(lambda l: len(l) > 0 and not l.endswith('files read'),
                         output.split('\n')))

    # Make ExifTool give consistent format for one/multi-files
    if len(paths) == 1:
        output.insert(0, f"======= {paths[0]}")

    # Pop works on end of the list, so reverse it
    output = list(reversed(output))
    while len(output) > 0:
        active_path = pathlib.Path(output.pop().split(' ',1)[1])
        tags, values = list(), list()
        while len(output) > 0 and output[-1][0] != '=':
            line = output.pop()
            if ':' in line:
                tag, value = line.split(':',1)
                tags.append(tag.rstrip())
                values.append(value.rstrip())
            else:
                values[-1] += line
        lookup[active_path] = dict(zip(tags,values))
    '''
    return lookup

def attribute_file(all_table_data: Dict[str, pd.DataFrame],
                   fpath: pathlib.Path,
                   exiftool_data: Dict[pathlib.Path,str],
                   ) -> None:
    # Given a file, search folders/entries to find it and print out all tags
    # and associated text_field data

    if not isinstance(fpath, pathlib.Path):
        fpath = pathlib.Path(fpath)

    # If folder is recognized, filter entries to include the folder
    filter_against = None
    for folder_id, folder in zip(all_table_data['folders']['id'],
                                 all_table_data['folders']['path']):
        if fpath.is_relative_to(folder):
            filter_against = folder_id
            fpath = fpath.relative_to(folder)
            break

    print(fpath)
    longest_line = len(str(fpath))

    # ExifTool attributes
    if (len(exiftool_data) == 0) or \
       (sum(pd.isna(_) for _ in exiftool_data.values()) == len(exiftool_data.values())):
        complaint = f"No relevant EXIF metadata for '{fpath}'"
        print(complaint)
        longest_line = max(longest_line, len(complaint))
    else:
        for (et_tag, et_val) in exiftool_data.items():
            metadata = f"EXIFTOOL {et_tag}: {et_val}"
            print(metadata)
            longest_line = max(longest_line, len(metadata))

    # Set series to utilize
    if filter_against is None:
        searchable = all_table_data['entries']['path']
        search_index = all_table_data['entries']['id']
    else:
        filter_boolean = (all_table_data['entries']['folder_id'] == filter_against)
        searchable = all_table_data['entries'][filter_boolean]['path']
        search_index = all_table_data['entries'][filter_boolean]['id']

    # Find match?
    matches = (searchable == str(fpath)).tolist()
    if sum(matches) == 0:
        complaint = f"Did not find '{fpath}' in entries list!"
        print(complaint)
        longest_line = max(longest_line, len(complaint))
        print('-'*longest_line)
        return
    hit = search_index[matches.index(True)]

    # Once we have a hit, make an output record for it
    # Find tags?
    tag_filter = (all_table_data['tag_entries']['entry_id'] == hit)
    if tag_filter.sum() == 0:
        complaint = f"No tags for '{fpath}'"
        print(complaint)
        longest_line = max(longest_line, len(complaint))
    else:
        tag_names = list()
        for tag_id in all_table_data['tag_entries'][tag_filter]['tag_id']:
            tag_names.append(all_table_data['tags'][all_table_data['tags']['id'] == tag_id]['name'].tolist()[0])
        metadata = f"TAGSTUDIO TAGS: {', '.join(tag_names)}"
        print(metadata)
        longest_line = max(longest_line, len(metadata))

    # Find text fields?
    text_filter = (all_table_data['text_fields']['entry_id'] == hit)
    if text_filter.sum() == 0:
        complaint = f"No text entries for '{fpath}'"
        print(complaint)
        longest_line = max(longest_line, len(complaint))
    else:
        for (idx, matching_entry) in all_table_data['text_fields'][text_filter].iterrows():
            metadata = f"TAGSTUDIO {matching_entry['type_key']}:"+"\t"+f"{matching_entry['value']}"
            print(metadata)
            longest_line = max(longest_line, len(metadata))

    print('-'*longest_line)

def build() -> argparse.ArgumentParser:
    # CLI

    prs = argparse.ArgumentParser()
    prs.add_argument('--tagstudio-db',
                     type=pathlib.Path,
                     default='.TagStudio/ts_library.sqlite',
                     help=f"TagStudio library to load (Default: %(default)s -- working directory)")
    prs.add_argument('--csv-path',
                     type=pathlib.Path,
                     default='.TagStudio/exiftool.csv',
                     help=f"ExifTool CSV mapping of information that can be updated from TagStudio DB (Default: %(default)s)")
    prs.add_argument('--export',
                     type=pathlib.Path,
                     default=None,
                     help="Path to export updated database to (SQLite file, defaults to value of --tagstudio-db)")
    prs.add_argument('--query-files',
                     type=pathlib.Path,
                     default=None,
                     nargs='*',
                     help='Files to look up logged data for in the TagStudio DB (recurses directories)')
    prs.add_argument('--exiftool-path',
                     type=pathlib.Path,
                     default='exiftool',
                     help="Path to ExifTool binary (unnecessary to specify if globally accessible)")
    return prs

def parse(args: argparse.Namespace = None,
          prs: argparse.ArgumentParser = None,
          ) -> argparse.Namespace:
    # Argument handling

    if prs is None:
        prs = build()
    if args is None:
        args = prs.parse_args()
    if args.export is None:
        args.export = args.tagstudio_db
    return args

def diriterate(query: pathlib.Path,
               all_table_data: Dict[str, pd.DataFrame],
               exiftool_lookup: Dict[pathlib.Path,Dict[str,str]],
               ) -> None:
    if query.is_dir():
        for subquery in query.iterdir():
            diriterate(subquery, all_table_data, exiftool_lookup)
    else:
        attribute_file(all_table_data, query, exiftool_lookup[query])

def main(args: argparse.Namespace) -> None:
    # Load TagStudio DB as PRIMARY Source of Truth
    cur, all_table_data = sqlite_db_load(args.tagstudio_db)
    # Map TagStudio DB to format for use in ExifTool
    tagstudio_map_to_csv(args.csv_path, all_table_data)
    # Use ExifTool to fetch metadata from queried disk files
    exiftool_lookup = exiftool_map_from_disk(args.query_files,
                                             args.exiftool_path)
    # Recursion permitted
    for query in args.query_files:
        diriterate(query, all_table_data, exiftool_lookup)
    if args.export is None:
        print(f"--export is required for map-out")
        exit(1)
    print("Update metadata on files? ")
    ans = input()
    if ans == 'yes':
        exiftool_map_from_database(args.csv_path, args.query_files, args.exiftool_path)
    print(f"Share-able and merge-able database available at {args.export}")
    exit(0)

if __name__ == "__main__":
    main(parse())

