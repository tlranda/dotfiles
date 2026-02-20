# Dependent libraries
import pandas as pd

# Builtin libraries
import datetime
import hashlib
import os
import pathlib
import sqlite3
from typing import Callable, Dict, List, Optional, Tuple, Union
import warnings

"""
    To play with ExifTool:

    Map-Out:
        Load entries (to know what files go where), maybe folders too
        Load tags to decide what tags should be exported
        Load tag_entries to see mappings that need to be updated
        Load text_fields to see other metadata to export

    Map-In:
        Load entries (to know what files go where), maybe folders too
        For each file, load it in ExifTool and check for its tags etc
            Pool all unique tags under a dict (tag: path)
            Also pool other text_fields for import (path: list of fields)
            Both of these ONLY for new/changed values
        Ensure correct values are ready to go, then update sqlite database
"""


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
                      with_con: bool = False
                      ) -> Union[sqlite3.Cursor,
                                  Tuple[sqlite3.Cursor, sqlite3.Connection]]:
    # SQLite helper to initiate db connection
    con = sqlite3.connect(fname)
    if with_con:
        return con.cursor(), con
    return con.cursor()

def get_tables(cur: sqlite3.Cursor
               ) -> pd.DataFrame:
    # SQLite helper: Fetch all of the tables from given cursor's main schema

    # Expect columns based on SQLite version 3.37.0 (2021/11/27) documentation
    # More columns may be added in the future
    expect_columns = ['schema','name','type','ncol','wr','strict']
    cur.execute('PRAGMA main.table_list;')
    records = cur.fetchall()
    return pd.DataFrame.from_records(records, columns=expect_columns)

def get_table_description(cur: sqlite3.Cursor,
                          name: str
                          ) -> pd.DataFrame:
    # SQLite helper: Fetch table schema for main schema's table of given name

    expect_columns = ['index','name','type','notnull','default_value','pk']
    cur.execute(f'PRAGMA main.table_info({name});')
    records = cur.fetchall()
    return pd.DataFrame.from_records(records, columns=expect_columns)

def get_table_data(cur: sqlite3.Cursor,
                   name: str,
                   table_descriptions : Optional[Dict[str, pd.DataFrame]] = None
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
                   update_hexdigest: bool = False,
                   hashfunc: Optional[Callable] = None,
                   force_rehash: bool = False
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
    #    all_table_data[table_name] = get_table_data(cur, table_name)

    # Update modified times and hexdigests as necessary
    if update_hexdigest or force_rehash:
        if hashfunc is None:
            raise ValueError("Must specify a hashfunc to update hexdigests")

        # First time: No hexdigests available!
        if 'hexdigest' not in all_table_data['entries']:
            # TagStudio does not currently have a column for hexdigests
            ins_col_index = (all_table_data['entries'].columns
                             ).tolist().index('date_modified')
            needed_rows = len(all_table_data['entries'])
            all_table_data['entries'].insert(ins_col_index,
                                             'hexdigest',
                                             [None] * needed_rows)
            updated = tagstudio_index_hexdigests(all_table_data,
                                                 hashfunc,
                                                 force=False)
        elif force_rehash:
            # Force should be triggered on hashing library changes
            updated = tagstudio_index_hexdigests(all_table_data,
                                                 hashfunc,
                                                 force=True)
        else:
            # Regular check for new/modified data
            updated = tagstudio_index_hexdigests(all_table_data,
                                                 hashfunc,
                                                 force=False)

        # Save back to disk
        if len(updated) > 0:
            sqlite_db_save(dbname,
                           all_table_data)

    return cur, all_table_data

def sqlite_db_save(dbname: str,
                   dbdatadict: Dict[str, pd.DataFrame]
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
    TAGSTUDIO INFORMATION

--TAGSTUDIO'S SQLITE LAYOUT--
folders: id, path, uuid
entries: folder_id, path, filename, suffix, date_created, date_modified, date_added[, hexdigest]
text_fields: value, id, type_key, entry_id, position
tags: id, name, shorthand, color_namespace, color_slug, is_category, icon, disambiguation_id
tag_entries: tag_id, entry_id

"""

def tagstudio_index_hexdigests(all_table_data: Dict[str, pd.DataFrame],
                               hashfunc: Callable,
                               force: bool = False
                               ) -> List[int]:
    # Iterates over entry/folder tables to determine if digests are up-to-date
    # Indicate updated entry indices if any are changed
    updated = list()

    # Technically you can merge the DFs, but I think this approach is simpler
    # to read than merging and unlikely to differ dramatically in performance
    # merge = all_table_data['entries'].set_index('folder_id').join(
    #               all_table_data['folders'].set_index('id'), lsuffix='_file',
    #               rsuffix='_folder')
    # merge.insert(0, 'path', merge['path_folder'].apply(pathlib.Path) / merge['path_file'])
    # merge.index = all_table_data['entries']['id']
    # merge.drop(columns=['path_file','path_folder'])
    # entry_paths = dict((id,path) for (id, path) in zip(merge['id'],merge['path']))
    folder_remap = dict((idx, pathlib.Path(path)) for (idx, path) in \
                                zip(all_table_data['folders']['id'],
                                    all_table_data['folders']['path']))
    entry_paths = dict((idx, folder_remap[folder_id] / pathlib.Path(path))
                       for (idx, folder_id, path) in \
                                zip(all_table_data['entries']['id'],
                                    all_table_data['entries']['folder_id'],
                                    all_table_data['entries']['path']))

    for (entry_id, entry_path) in entry_paths.items():
        if not entry_path.exists():
            print(f"Entry ID: {entry_id} @ {entry_path}: NOT FOUND")
            continue

        entry_index = (all_table_data['entries']['id'] == entry_id).tolist().index(True)
        last_modified = all_table_data['entries'].loc[entry_index, 'date_modified']
        mtime = datetime.datetime.fromtimestamp(os.stat(entry_path).st_mtime)
        if not force and (not pd.isnull(last_modified) and mtime <= last_modified):
            # No need to re-hash
            hexd = all_table_data['entries'].loc[entry_index,'hexdigest']
            # Overly verbose
            #print(f"Entry ID: {entry_id} @ {entry_path} (Last modified: {mtime}): {hexd} |NORESCAN|")
            continue

        # Update last modified time AND digest value
        with open(entry_path, 'rb') as f:
            hexd = hashfunc(f.read()).hexdigest()
        print(f"Entry ID: {entry_id} @ {entry_path} (Last modified: {mtime}): {hexd}")
        all_table_data['entries'].loc[entry_index,['date_modified','hexdigest']] = [mtime, hexd]
        updated.append(entry_index)

    return updated

def create_exports(all_table_data: Dict[str, pd.DataFrame],
                   export_tables: Dict[str, pd.DataFrame]
                   ) -> Dict[str, pd.DataFrame]:
    # Idea is to replace 'entry_id' links in the tagstudio hierarchy with the
    # hexdigest throughout all tables, then export all tables

    # One-time lookup for how to remap
    remap = dict((row.id, row.hexdigest) \
                    for (rowid, row) \
                    in all_table_data['entries'].loc[:,['id','hexdigest']].iterrows())

    # NON-EXPORT: folders
    # DIRECT EXPORT: tags
    export_tables['tags'] = all_table_data['tags']
    # EDIT, THEN EXPORT: entries, text_fields, tag_entries
    for tbl_name, col in zip(['tag_entries','text_fields', 'entries'],
                             ['entry_id', 'entry_id', 'id']):
        tbl = all_table_data[tbl_name].copy()
        # Upcast the datatype so that integer columns can accept string hash data
        tbl[col] = tbl[col].astype(str)

        # Cannot naively use pd.DataFrame.map(); TagStudio may persist some data
        # in related tables even after the entry table ceases to track an ID
        drop_rows = list()
        for (idx, row) in tbl.iterrows():
            # Re-convert to integer for lookup
            eid = int(row[col])
            if eid in remap:
                tbl.loc[idx,col] = remap[eid]
            else:
                drop_rows.append(idx)
        if tbl_name == 'entries':
            tbl = tbl.drop(columns=['folder_id','path','hexdigest'])
        export_tables[tbl_name] = tbl.drop(index=drop_rows).reset_index(drop=True)

    return export_tables

"""
--TAGSTUDIO'S SQLITE LAYOUT--
folders: id, path, uuid
entries: id, folder_id, path, filename, suffix, date_created, date_modified, date_added[, hexdigest]
tags: id, name, shorthand, color_namespace, color_slug, is_category, icon, disambiguation_id
text_fields: value, id, type_key, entry_id, position
tag_entries: tag_id, entry_id
"""

def merge_with_imported_data(all_table_data: Dict[str, pd.DataFrame],
                             imported_tables: Dict[str, pd.DataFrame]
                             ) -> Dict[str, pd.DataFrame]:
    # Join local data to foreign data from imported tables on the hexdigest as key
    # Create a list of tags that are utilized by the affected entries, ask to import any that don't exist
    # For each matched piece, ask to import any text_fields that do not exist already

    # From scratch: TAGS
    import_tags        = imported_tables['tags']
    import_entries     = imported_tables['entries']
    import_tag_entries = imported_tables['tag_entries']

    # Map tags between datasets
    existing_tags        = all_table_data['tags']
    existing_entries     = all_table_data['entries']
    existing_tag_entries = all_table_data['tag_entries']
    # DEBUG: Trigger a deletion so that an entry is made
    deleted_entry_tag = existing_tag_entries.loc[0,'tag_id']
    deleted_entry_id  = existing_tag_entries.loc[0,'entry_id']
    existing_tag_entries = existing_tag_entries.drop(index=[0]).reset_index(drop=True)
    """
(Pdb) existing_tags
     id                   name shorthand     color_namespace    color_slug  is_category  icon disambiguation_id
0     0               Archived      None  tagstudio-standard           red            0  None              None
1     1               Favorite      None  tagstudio-standard        yellow            0  None              None
2     2              Meta Tags      None                None          None            1  None              None
3  1000             Attributed            tagstudio-standard         green            0  None              None
4  1001  Uncertain Attribution             tagstudio-pastels  light-yellow            0  None              None
5  1002             Duplicate?             tagstudio-pastels      lavender            0  None              None
6  1003    MISSING ATTRIBUTION            tagstudio-standard    red-orange            0  None              None
(Pdb) import_tags
     id                   name shorthand     color_namespace    color_slug  is_category  icon disambiguation_id
0     0               Archived      None  tagstudio-standard           red            0  None              None
1     1               Favorite      None  tagstudio-standard        yellow            0  None              None
2     2              Meta Tags      None                None          None            1  None              None
3  1000             Attributed            tagstudio-standard         green            0  None              None
4  1001  Uncertain Attribution             tagstudio-pastels  light-yellow            0  None              None
5  1002             Duplicate?             tagstudio-pastels      lavender            0  None              None
6  1003    MISSING ATTRIBUTION            tagstudio-standard    red-orange            0  None              None
    """
    # import_tag_id : optional(existing_tag_id)
    tag_map = dict()
    tag_additions = pd.DataFrame(columns=existing_tags.columns)
    for (irowidx, irowdata) in import_tags.iterrows():
        candidate_id = irowdata['id']
        candidate_name = irowdata['name']

        found = existing_tags[existing_tags['name'] == candidate_name]
        if len(found) == 0:
            tag_map[candidate_id] = None
        else:
            tag_map[candidate_id] = found['id'].tolist()[0]
    """
(Pdb) import_entries
                                   id                    filename suffix date_created              date_modified                 date_added
[638 rows x 6 columns]
(Pdb) existing_entries
      id  folder_id                                      path                    filename suffix date_created                         hexdigest              date_modified                 date_added
[638 rows x 9 columns]
    """
    # import hex : existing entry_id
    entry_map = dict()
    for (irowidx, irowdata) in import_entries.iterrows():
        # Try for a hex match first
        candidate_hex = irowdata['id']
        found = existing_entries[existing_entries['hexdigest'] == candidate_hex]
        if len(found) == 1:
            entry_map[candidate_hex] = found['id'].tolist()[0]
            continue
        # While a hex match SHOULD be sufficient, we can also try to match on name+suffix+date_created+date_modified
        candidate_name   = irowdata['filename']
        candidate_suffix = irowdata['suffix']
        candidate_dc     = irowdata['date_created']
        candidate_dm     = irowdata['date_modified']
        found = existing_entries[(existing_entries['filename'] == candidate_name) &
                              (existing_entries['suffix'] == candidate_suffix) &
                              (existing_entries['date_created'] == candidate_dc) &
                              (existing_entries['date_modified'] == candidate_dm)]
        if len(found) == 1:
            entry_map[candidate_hex] = found['id'].tolist()[0]

    # Now that we can handle tag IDs, link up the tag entries
    imported_tag_entries = pd.DataFrame(columns=existing_tag_entries.columns)
    """
(Pdb) import_tag_entries
     tag_id                          entry_id
[265 rows x 2 columns]
(Pdb) existing_tag_entries
     tag_id  entry_id
[267 rows x 2 columns]
    """
    new_tag_entries = pd.DataFrame(columns=existing_tag_entries.columns)
    for (irowidx, irowdata) in import_tag_entries.iterrows():
        try:
            candidate_remapped_tag_id = tag_map[irowdata['tag_id']]
            candidate_remapped_entry_id = entry_map[irowdata['entry_id']]
        except KeyError:
            # Non-importable!
            continue

        found = existing_tag_entries[existing_tag_entries['entry_id'] == candidate_remapped_entry_id]
        if len(found) == 0 or candidate_remapped_tag_id not in found['tag_id']:
            # Novel tag: we'll need to import it in the tags table later
            if candidate_remapped_tag_id is None:
                import_record = import_tags[import_tags['id'] == irowdata['tag_id']]
                candidate_remapped_tag_id = import_record['id']
                while candidate_remapped_tag_id in existing_tags['id']:
                    candidate_remapped_tag_id += 1
                import_record['id'] = candidate_remapped_tag_id
                # Mark import requirement as handled; inclusion in tag_additions signals update to tags table
                tag_additions = pd.concat((tag_additions, import_record))
                tag_map[irowdata['tag_id']] = candidate_remapped_tag_id
            import pdb
            pdb.set_trace()
            print(f"Would import tag id {candidate_remapped_tag_id} (Friendly name: '{existing_tags[existing_tags['id'] == candidate_remapped_tag_id]['name'].tolist()[0]}')"
                  f"for entry id {candidate_remapped_entry_id} (Friendly name: '{existing_tag_entries[existing_tag_entries['entry_id'] == candidate_remapped_entry_id]['path'].tolist()[0]}')")
            new_series = pd.Series(index=new_tag_entries.columns)
            for col in new_tag_entries.columns:
                if col in ['tag_id','entry_id']:
                    if col == 'tag_id':
                        new_series[col] = candidate_remapped_tag_id
                    else:
                        new_series[col] = candidate_remapped_entry_id
                else:
                    new_series[col] = irowdata[col]
            new_tag_entries = pandas_append_series_to_end_of_frame(new_tag_entries,
                                                                   new_series)
    print("New entries:")
    print(new_tag_entries)
    exit(0)

    # TODO: This thing... it ain't working

    # First, trim imported tables data down to items that we can match in our library
    remap = dict() # Hash : all_table_data['entries']['entry_id']
    # Expect imported_tables['entries'].loc[179] == all_table_data['entries'].loc[185]
    all_hex_digest = all_table_data['entries']['hexdigest'].tolist()
    all_index = all_table_data['entries']['id'].tolist()
    for rowidx, row in imported_tables['entries'].iterrows():
        digest = row.id
        try:
            index = all_hex_digest.index(digest)
        except ValueError:
            print(f"Drop import for hash {digest} (Expect filename match: {row.filename}) -- not found in local library!")
            continue
        remap[digest] = all_index[index]
    reverse_remap = dict((v,k) for (k,v) in remap.items()) # DEBUG STRUCTURE
    remap_index = list(remap.values())

    # Use remap with text_fields and tag_entries to migrate common entries as needed
    text = all_table_data['text_fields']
    import_text = imported_tables['text_fields']
    for (rowidx, row) in import_text.iterrows():
        import_text_value = row.value
        import_text_kind = row.type_key

        all_entry_id = remap[row.entry_id]
        text_filter = (text['entry_id'] == all_entry_id)
        existing_texts = text[text_filter]
        print(f"Row {row.entry_id} remaps to all data {all_entry_id} with {len(existing_texts)} hits in all_table_data already")

        # Probably performance-inefficient operation
        new = pd.concat((row.to_frame().T.drop(columns='entry_id'),
                         existing_texts.drop(columns=['entry_id']))
                        ).drop_duplicates(keep=False)
        if len(new) > 0:
            import pdb
            pdb.set_trace()
            new.insert(existing_texts.columns.tolist().index('entry_id'),
                       'entry_id',
                       [all_entry_id] * len(new))
            #import pdb
            #pdb.set_trace()
            #text = pd.concat((text, new))
            print("Would import entries:\n"+f"{new}")

def attribute_file(all_table_data: Dict[str, pd.DataFrame],
                   fpath: Union[str,pathlib.Path]
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
        print('-'*len(complaint))
        return
    hit = search_index[matches.index(True)]

    # Once we have a hit, make an output record for it
    print(fpath)
    # Find tags?
    tag_filter = (all_table_data['tag_entries']['entry_id'] == hit)
    if tag_filter.sum() == 0:
        print(f"No tags for '{fpath}'")
    else:
        tag_names = list()
        for tag_id in all_table_data['tag_entries'][tag_filter]['tag_id']:
            tag_names.append(all_table_data['tags'][all_table_data['tags']['id'] == tag_id]['name'].tolist()[0])
        print(f"TAGS: {', '.join(tag_names)}")

    # Find text fields?
    text_filter = (all_table_data['text_fields']['entry_id'] == hit)
    if text_filter.sum() == 0:
        print(f"No text entries for '{fpath}'")
    else:
        for (idx, matching_entry) in all_table_data['text_fields'][text_filter].iterrows():
            print(f"{matching_entry['type_key']}:"+"\t"+f"{matching_entry['value']}")
    print('-'*len(str(fpath)))

if __name__ == "__main__":
    import argparse

    prs = argparse.ArgumentParser()
    prs.add_argument('--tagstudio-db', type=pathlib.Path,
                     default='.TagStudio/ts_library.sqlite',
                     help=f"TagStudio library to load (Default: %(default)s -- working directory)")
    prs.add_argument('--query-file', type=pathlib.Path,
                     default=None, nargs='*', help='Files to look up logged data for')
    prs.add_argument('--export', type=pathlib.Path,
                     default=None, help="Path to export hash-dataset to (SQLite file)")
    prs.add_argument('--override-export', action='store_true',
                     help="Rebuild export database from scratch rather than updating in place (REQUIRED for hashlib changes)")
    prs.add_argument('--import', dest='import_', type=pathlib.Path,
                     default=None, help="Path to import hash-dataset from (SQLite file)")
    hashfuncs = sorted(hashlib.algorithms_available)
    prs.add_argument('--hash-library', choices=hashfuncs, default=hashfuncs[0],
                     help="Hash function to use on data in export (Default: %(default)s)")
    args = prs.parse_args()

    # Default to runtime arg
    hashfunc = getattr(hashlib, args.hash_library)
    if args.import_ is not None:
        _, imported_tables = sqlite_db_load(args.import_)
        desired_hashfunc = imported_tables['merge_settings']['hashlib'].iloc[0]
        print(f"Using hash func {args.hash_library} to merge with import library's hash func {desired_hashfunc}")
        if args.hash_library != desired_hashfunc:
            if args.override_export:
                hashfunc = getattr(hashlib, desired_hashfunc)
            else:
                raise ValueError(f"Imported data uses hash function {desired_hashfunc}, which differs from selected function {args.hash_library}!"
                                 "\nEnsure the functions match or use --override-export flag to re-index your own library using the imported library's hash function")

    if args.export is not None:
        if args.override_export or not args.export.exists():
            export_tables = {'merge_settings':
                                pd.DataFrame({'hashlib': [args.hash_library],
                                             },
                                             index=[0])}
        else:
            _, export_tables = sqlite_db_load(args.export)
            if not args.override_export:
                desired_hashfunc = export_tables['merge_settings']['hashlib'].iloc[0]
                if desired_hashfunc != args.hash_library:
                    warnings.warn(f"Changing runtime hash function ({args.hash_library}) to match previous export settings ({desired_hashfunc})."
                                  "\nTo disable this behavior, use flag --override-export",
                                  UserWarning)
                    hashfunc = getattr(hashlib, desired_hashfunc)

    # All functions require the initial tagstudio load
    cur, all_table_data = sqlite_db_load(args.tagstudio_db,
                                         update_hexdigest=True,
                                         hashfunc=hashfunc,
                                         force_rehash=args.override_export)

    if args.export is not None:
        export_tables = create_exports(all_table_data, export_tables)
        sqlite_db_save(args.export, export_tables)
        print(f"Share-able and merge-able database available at {args.export}")
        exit(0)
    if args.import_ is not None:
        merge_with_imported_data(all_table_data, imported_tables)
        exit(0)

    for query in args.query_file:
        attribute_file(all_table_data, query)

