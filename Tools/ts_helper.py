# Dependent libraries
import pandas as pd
# Why no PyExifTool? It does not re-implement ExifTool and STILL requires your install
# Otherwise, it's over-engineered compared to current support plans.
# Ideally, we strip Pandas out later, but I'm willing to accept the overhead as
# it is easy to request and actually provides a lot of value that is harder to
# replicate separately

# NOTE: Unix permissions 775 needed on all paths at/above images for ExifTool
# to be able to write its data out to disk. Images of course need read permission.
# Windows is likely similar.

# File format acceptability:
# KNOWN OK R/W: GIF, JPEG/JPG, PNG, M4A, MP4, PDF, WEBP
# KNOWN READ-ONLY: AIFF, MP3, OGG, WAV, WEBM
# MORE TESTING NEEDED: AVIF
# UNTESTED: JPEG2000/JXL, PPM, PSD, TIFF

# Special formats:
# Dates: YYYY:mm:dd HH:MM:SS[.ss][+/-HH:MM]
# lang-alt: Indicates tag can be suffixed to different languages, which may be a source of confusion for cross-national traffic
# Structs have to be individually flat-specified or fully-specified, and may require `-struct` command-line-argument for ExifTool to read later
# Boolean: 'Yes', 'No' values

# TODO: Migrate into complete set of XMP tags
"""
+ indicates a List tag that can be appended to
/ indicates a tag ExifTool will edit, but preferably avoid creating if another same-name tag can be created instead
! indicates a tag that is generally unsafe to write to under normal circumstances as they can affect data processing / rendering
* indicates protected tag which is handled automatically by ExifTool
: indicates a mandatory tag which may be added automatically when writing

28 common writable tags:
  About                        (XMP rdf string!) -- DO NOT USE!
+ AttributionURL               (XMP cc string)
+ Author                       (XMP pdf string)
+ BaseURL                      (XMP xmp string)
  Caption                      (XMP acdsee string/)
+ Description                  (XMP crd/dc/xmp lang-alt)
  DOI                          (XMP prism string/)
  Label                        (XMP xmp string)
  LabelName1                   (XMP ics string_+)
  LabelName2                   (XMP ics string_+)
  LabelName3                   (XMP ics string_+)
  LabelName4                   (XMP ics string_+)
  LabelName5                   (XMP ics string_+)
  LabelName6                   (XMP ics string_+)
  Lyrics                       (XMP xmpDM string)
+ MetadataAuthorityIdentifier  (XMP iptcExt string_+)
+ MetadataAuthorityName        (XMP iptcExt lang-alt_)
+ MetadataDate                 (XMP xmp date)
+ MetadataLastEdited           (XMP iptcExt date)
+ MetadataLastEditorIdentifier (XMP iptcExt string_+)
+ MetadataLastEditorName       (XMP iptcExt lang-alt_)
+ MetadataModDate              (XMP xmpDM date)
+ Notes                        (XMP acdsee string/)
+ Tagged                       (XMP acdsee boolean/)
+ TagsList                     (XMP digiKam string+)
+ Transcript                   (XMP iptcExt lang-alt)
+ TranscriptLink               (XMP iptcExt QualifiedLink struct)
+ URLUrl                       (XMP prism string/_+)
"""

# TODO: Refactor as such:
# ./interface/cli.py - CLI for use as terminal tool
# ./interface/app.py - GUI app to-be-developed
# ./interface/discord.py - Discord bot version
# ./interface/web.py - Website
# ./backend/pdutil.py - Pandas Helpers
# ./backend/sqlite.py - SQLite Helpers
# ./backend/exiftool.py - ExifTool Helpers
# ./backend/tagstudio.py - TagStudio Helpers

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
    # There's probably a better way to do this, but this pattern shows up a lot
    # and it is ugly AF
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
    con = sqlite3.connect(fname)
    if with_con:
        return con.cursor(), con
    return con.cursor()

def get_tables(cur: sqlite3.Cursor,
               ) -> pd.DataFrame:
    # Fetch all of the tables from given cursor's main schema
    # Expect columns based on SQLite version 3.37.0 (2021/11/27) documentation
    # More columns may be added in the future
    expect_columns = ['schema','name','type','ncol','wr','strict']
    cur.execute('PRAGMA main.table_list;')
    records = cur.fetchall()
    return pd.DataFrame.from_records(records, columns=expect_columns)

def sqlite_db_load(dbname: Union[str, pathlib.Path],
                   ) -> Tuple[sqlite3.Cursor, Dict[str, pd.DataFrame]]:
    cur = get_db_connection(dbname)
    avail_tables = get_tables(cur)
    cur.close()
    all_table_data = dict()
    # Pandas does not support retrieving the sqlite_schema, but we do not need it
    skip_names = ['sqlite_schema']
    for table_name in avail_tables['name']:
        if table_name in skip_names:
            continue
        # Pandas only supports URIs for now; cannot reuse sqlite cursor/connection
        all_table_data[table_name] = pd.read_sql_table(table_name,
                                                       f"sqlite:///{dbname}")
    return all_table_data

def sqlite_db_save(dbname: str,
                   dbdatadict: Dict[str, pd.DataFrame],
                   ) -> None:
    cur, con = get_db_connection(dbname, with_con=True)
    PROTECTED_TABLES = ['sqlite_sequence']
    for tblname, tbldata in dbdatadict.items():
        if tblname in PROTECTED_TABLES:
            continue
        tbldata.to_sql(tblname, con, if_exists='replace',
                       index=False, method='multi')
"""
    ExifTool Interface and Assistance

    ExifTool supports TONs of formats, see its documentation for full coverage.
    THIS interface for ExifTool attempts to use a single set of keys for
    accessing metadata, which may not always be available for all file formats.

    The common EXIF metadata keys should work for most typical formats, including:
        * PNG
        * GIF
        * MP3/MP4
    With caveats:
        * JPG/JPEG
            + Source field can be truncated
            + URL field is OK (redundancy)
            + Accounted for in parity checks by this program
    Known to have issues with:
        * WEBP (No URL/Source fields)
        * WAV (unsupported)
"""
# Values should correspond to keys in function `tagstudio_to_exiftool_dict()`
exiftool_mappings = {
    'Artist': ['creator','contributor',],
    'Source': ['source',],
    # NOTE: URL is not always supported (GIF, MP4, etc)
    'URL': ['source',],
    'Description': ['tags',],
    }

def exiftool_update_from_csv(csv_path: pathlib.Path,
                             disk_paths: Optional[Union[pathlib.Path, List[pathlib.Path]]],
                             exiftool_path: pathlib.Path,
                             allow_overwrite: bool,
                             ) -> None:
    if disk_paths is None:
        return
    if not isinstance(disk_paths, list):
        disk_paths = [path]

    # Batch-call ExifTool on all indicated files
    cmd = [exiftool_path, f'-csv={csv_path}']+[f'-{tag}' for tag in exiftool_mappings.keys()]
    if allow_overwrite:
        cmd += ['-overwrite_original_in_place']
    cmd += [str(_) for _ in disk_paths]
    print(" ".join([str(_) for _ in cmd]))
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
    print(" ".join([str(_) for _ in cmd]))
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise ValueError(f"ExifTool return code: {proc.returncode}")
    output = proc.stdout.decode('utf-8')
    df = pd.read_csv(StringIO(output))
    for idx, row in df.iterrows():
        lookup[pathlib.Path(row['SourceFile'])] = dict((k,v) for (k,v) in row.to_dict().items() if k != 'SourceFile' and not pd.isna(v))
    return lookup

def exiftool_format_tables(all_table_data: Dict[str, pd.DataFrame],
                           fpath: pathlib.Path,
                           ) -> Dict[str,str]:
    exiftool_like = dict()
    # Find entity ID from tables
    try:
        entry_id = tagstudio_lookup_entry_id(all_table_data, fpath)
    except ValueError:
        # Not found == no tagstudio data
        return exiftool_like

    # Collect tags and text fields for the entry
    try:
        tags = tagstudio_lookup_tags(all_table_data, entry_id)
    except ValueError:
        tags = list()
    try:
        fields = tagstudio_lookup_text_fields(all_table_data, entry_id)
    except ValueError:
        fields = dict()

    # Map ExifTool keys to Tagstudio fields / tag format
    for key in exiftool_mappings.keys():
        match key:
            case 'Artist':
                if 'ARTIST' in fields:
                    exiftool_like[key] = fields['ARTIST']
                elif 'AUTHOR' in fields:
                    exiftool_like[key] = fields['AUTHOR']
            case 'Source' | 'URL':
                if 'URL' in fields:
                    exiftool_like[key] = fields['URL']
            case 'Description':
                if len(tags) > 0:
                    exiftool_like[key] = ";".join(tags)+";"
    return exiftool_like

"""
    TagStudio DF Interface

GENERAL EXPECTATION OF TagStudio's SQLITE SCHEMA
folders: id, path, uuid
entries: folder_id, path, filename, suffix, date_created, date_modified, date_added
text_fields: value, id, type_key, entry_id, position
tags: id, name, shorthand, color_namespace, color_slug, is_category, icon, disambiguation_id
tag_entries: tag_id, entry_id
"""

def tagstudio_lookup_entry_id(all_table_data: Dict[str, pd.DataFrame],
                              fpath: pathlib.Path,
                              ) -> int:
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
    # Set series to utilize
    if filter_against is None:
        searchable = all_table_data['entries']['path']
        search_index = all_table_data['entries']['id']
    else:
        filter_boolean = (all_table_data['entries']['folder_id'] == filter_against)
        searchable = all_table_data['entries'][filter_boolean]['path']
        search_index = all_table_data['entries'][filter_boolean]['id']
    matches = (searchable == str(fpath)).tolist()
    if sum(matches) == 0:
        raise ValueError(f"Did not find '{fpath}' in entries table!")
    return search_index[matches.index(True)]

def tagstudio_lookup_tags(all_table_data: Dict[str, pd.DataFrame],
                          entry_id: int
                          ) -> List[str]:
    tag_filter = (all_table_data['tag_entries']['entry_id'] == entry_id)
    if tag_filter.sum() == 0:
        raise ValueError("No tags found")
    tag_names = list()
    for tag_id in all_table_data['tag_entries'][tag_filter]['tag_id']:
        tag_names.append(all_table_data['tags'][all_table_data['tags']['id'] == tag_id]['name'].tolist()[0])
    return tag_names

def tagstudio_lookup_text_fields(all_table_data: Dict[str, pd.DataFrame],
                                 entry_id: int,
                                 ) -> Dict[str,str]:
    text_filter = (all_table_data['text_fields']['entry_id'] == entry_id)
    if text_filter.sum() == 0:
        raise ValueError("No text entries")
    text_fields = dict()
    for (idx, matching_entry) in all_table_data['text_fields'][text_filter].iterrows():
        text_fields[matching_entry['type_key']] = matching_entry['value']
    return text_fields

def tagstudio_to_exiftool_dict() -> Dict[str,str]:
    return {'creator': "",
            'contributor': "",
            'source': "",
            'tags': "",
            }

def tagstudio_and_exiftool_parity(tagstudio_as_exif_dict: Dict[str,str],
                                  exiftool_dict: Dict[str,str],
                                  ) -> bool:
    if 'Artist' in tagstudio_as_exif_dict:
        if ('Artist' not in exiftool_dict) or \
           (tagstudio_as_exif_dict['Artist'] != exiftool_dict['Artist']):
            return False
    if 'Description' in tagstudio_as_exif_dict:
        if ('Description' not in exiftool_dict) or \
           (tagstudio_as_exif_dict['Description'] != exiftool_dict['Description']):
            return False

    # Some formats do not have space to fully represent Source, so fall-back to URL is OK
    # As long as any pair of Source/URLs match, it's OK
    ts_urls = set([tagstudio_as_exif_dict[k] for k in ['Source','URL'] if k in tagstudio_as_exif_dict])
    ex_urls = set([exiftool_dict[k] for k in ['Source','URL'] if k in exiftool_dict])
    if max(map(len,[ts_urls,ex_urls])) > 0 and len(ts_urls.intersection(ex_urls)) == 0:
        return False
    return True

def tagstudio_map_to_csv(csv_path: pathlib.Path,
                         tagstudio_db: Dict[str,pd.DataFrame],
                         ) -> None:
    per_file = dict()
    # Map tag entries -> description
    tag_pairs = list(tagstudio_db['tags'][['id','name']].T.to_dict().values())
    tag_mapping = dict()
    for pair in tag_pairs:
        tag_mapping[pair['id']] = pair['name']
    # Map entry_id -> path
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
                per_file[path] = tagstudio_to_exiftool_dict()
            proposed_tag = f"{tag};"
            if proposed_tag not in per_file[path]['tags']:
                per_file[path]['tags'] += proposed_tag
    # Mark other fields from TagStudio text fields
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
                per_file[path] = tagstudio_to_exiftool_dict()
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

def tagstudio_db_update(tagstudio_db: pathlib.Path,
                        to_merge: List[pathlib.Path],
                        exiftool_lookup: Dict[pathlib.Path,Dict[str,str]],
                        all_table_data: Dict[str,pd.DataFrame],
                        ) -> None:
    # Update the all_table_data based on exiftool values
    print(f"NOT IMPLEMENTED -- saving with NO CHANGES")
    sqlite_db_save(tagstudio_db, all_table_data)

"""
    Viewer Logic
"""

def attribute_file(all_table_data: Dict[str, pd.DataFrame],
                   fpath: pathlib.Path,
                   exiftool_data: Dict[pathlib.Path,str],
                   ) -> None:
    # Given a file, search folders/entries to find it and print out all tags
    # and associated text_field data
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
            if pd.isna(et_val):
                continue
            metadata = f"EXIFTOOL {et_tag}:"+" "*(12-len(et_tag))+f"{et_val}"
            print(metadata)
            longest_line = max(longest_line, len(metadata))

    # Find entry match in TagStudioDB to extract metadata
    try:
        hit = tagstudio_lookup_entry_id(all_table_data, fpath)

        try:
            associated_text_fields = tagstudio_lookup_text_fields(all_table_data, hit)
            for field, value in associated_text_fields.items():
                metadata = f"TAGSTUDIO {field}:"+" "*(11-len(field))+f"{value}"
                print(metadata)
                longest_line = max(longest_line, len(metadata))
        except ValueError as e:
            complaint = f"{e.args[0]} for '{fpath}'"
            print(complaint)
            longest_line = max(longest_line, len(complaint))

        try:
            associated_tags = tagstudio_lookup_tags(all_table_data, hit)
            metadata = f"TAGSTUDIO TAGS:       {';'.join(associated_tags)+';'}"
            print(metadata)
            longest_line = max(longest_line, len(metadata))
        except ValueError as e:
            complaint = f"{e.args[0]} for '{fpath}'"
            print(complaint)
            longest_line = max(longest_line, len(complaint))
    except ValueError as VE:
        complaint = VE.args[0]
        print(complaint)
        longest_line = max(longest_line, len(complaint))
    print('-'*longest_line)

def diriterate(query: pathlib.Path,
               all_table_data: Dict[str, pd.DataFrame],
               exiftool_lookup: Dict[pathlib.Path,Dict[str,str]],
               merge_preference: str,
               to_merge: List[pathlib.Path],
               ) -> List[pathlib.Path]:
    if query.is_dir():
        for subquery in query.iterdir():
            to_merge = diriterate(subquery,
                                  all_table_data,
                                  exiftool_lookup,
                                  merge_preference,
                                  to_merge,
                                  )
    else:
        attribute_file(all_table_data, query, exiftool_lookup[query])

        # Figure out if merge is required or not for metadata update
        df_as_exiftool = exiftool_format_tables(all_table_data, query)
        if not tagstudio_and_exiftool_parity(df_as_exiftool, exiftool_lookup[query]):
            #print(f"! Mergeable: {query}")
            #print(df_as_exiftool)
            #print(exiftool_lookup[query])
            to_merge.append(query)
    return to_merge

"""
    CLI
"""

def build() -> argparse.ArgumentParser:
    prs = argparse.ArgumentParser()
    prs.add_argument('--exiftool-path',
                     type=pathlib.Path,
                     default='exiftool',
                     help="Path to ExifTool binary (unnecessary to specify if globally accessible)")
    prs.add_argument('--allow-exiftool-overwrite-in-place',
                     action='store_true',
                     help="Allow ExifTool to update files in place without preserving the original file (Default: %(default)s)")
    prs.add_argument('--tagstudio-db',
                     type=pathlib.Path,
                     default='.TagStudio/ts_library.sqlite',
                     help=f"TagStudio library to load (Default: %(default)s -- working directory)")
    prs.add_argument('--csv-path',
                     type=pathlib.Path,
                     default='.TagStudio/exiftool.csv',
                     help=f"ExifTool CSV mapping of information that can be updated from TagStudio DB (Default: %(default)s)")
    prs.add_argument('--merge-preference',
                     choices=['no-merge','exif','tagstudio'],
                     default='no-merge',
                     help=f"Which metadata takes precedence if not identical (Default: %(defaults))")
    prs.add_argument('query_files',
                     type=pathlib.Path,
                     default=None,
                     nargs='*',
                     help='Files to look up logged data for in the TagStudio DB (recurses directories)')
    return prs

def parse(args: argparse.Namespace = None,
          prs: argparse.ArgumentParser = None,
          ) -> argparse.Namespace:
    if prs is None:
        prs = build()
    if args is None:
        args = prs.parse_args()
    return args

def main(args: argparse.Namespace) -> None:
    # Load TagStudio DB and use ExifTool to retrieve in-file metadata
    all_table_data = sqlite_db_load(args.tagstudio_db)
    exiftool_lookup = exiftool_map_from_disk(args.query_files,
                                             args.exiftool_path)

    # Map TagStudio DB to format for use in ExifTool
    tagstudio_map_to_csv(args.csv_path, all_table_data)

    # Recursion permitted, accumulate a merge queue as we go
    merge_queue = list()
    for query in args.query_files:
        merge_queue = diriterate(query,
                                 all_table_data,
                                 exiftool_lookup,
                                 args.merge_preference,
                                 merge_queue)

    # Mass-produce updates based on merge strategy
    if args.merge_preference == 'exif':
        exiftool_update_from_csv(args.csv_path,
                                 merge_queue,
                                 args.exiftool_path,
                                 args.allow_exiftool_overwrite_in_place,
                                 )
    elif args.merge_preference == 'tagstudio':
        tagstudio_db_update(args.tagstudio_db,
                            merge_queue,
                            exiftool_lookup,
                            all_table_data,
                            )
    elif args.merge_preference == 'no-merge' and len(merge_queue) > 0:
        print(f"Metadata differs between TagStudio and ExifTool in {len(merge_queue)} files")
        print('\t* '+'\n\t* '.join([str(_) for _ in merge_queue]))
    else:
        print(f"All data up-to-date and merged in TagStudio and ExifTool")

if __name__ == "__main__":
    main(parse())

