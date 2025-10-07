# Dependent libraries
import pandas as pd

# Builtin libraries
import hashlib
import pathlib
import sqlite3

def get_db_connection(fname):
    try:
        con = sqlite3.connect(fname)
    except:
        raise
    return con.cursor()

def get_tables(cur):
    expect_columns = ['schema','name','type','ncol','wr','strict']
    cur.execute('PRAGMA main.table_list;')
    records = cur.fetchall()
    return pd.DataFrame.from_records(records, columns=expect_columns)

def get_table_description(cur, name):
    expect_columns = ['index','name','type','notnull','default_value','pk']
    cur.execute(f'PRAGMA main.table_info({name});')
    records = cur.fetchall()
    return pd.DataFrame.from_records(records, columns=expect_columns)

def get_table(cur, name, table_descriptions=None):
    if table_descriptions is None:
        table_descriptions = {
                name: get_table_description(cur, name)
                }

    expect_columns = list(table_descriptions[name]['name'])
    cur.execute(f'SELECT * FROM {name};')
    results = cur.fetchall()
    return pd.DataFrame.from_records(results, columns=expect_columns)

def tagstudio_load(dbname):
    cur = get_db_connection(dbname)
    avail_tables = get_tables(cur)
    table_descriptions = dict()
    for table_name in avail_tables['name']:
        table_descriptions[table_name] = get_table_description(cur, table_name)
    all_table_data = dict()
    for table_name in avail_tables['name']:
        all_table_data[table_name] = get_table(cur, table_name, table_descriptions)
    return cur, all_table_data

# TAGSTUDIO SQLITE LAYOUT
# folders: id, path, uuid
# entries: folder_id, path, filename, suffix, date_created, date_modified, date_added
# text_fields: value, id, type_key, entry_id, position
# tags: id, name, shorthand, color_namespace, color_slug, is_category, icon, disambiguation_id
# tag_entries: tag_id, entry_id
def tagstudio_index_hexdigests(all_table_data):
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
        with open(entry_path, 'rb') as f:
            md5sum = hashlib.md5(f.read()).hexdigest()
        print(f"Entry ID: {entry_id} @ {entry_path}: {md5sum}")

def attribute_file(all_table_data, fpath):
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
    args = prs.parse_args()
    cur, all_table_data = tagstudio_load(args.tagstudio_db)

    if args.query_file is None:
        tagstudio_index_hexdigests(all_table_data)
        exit(0)
    for query in args.query_file:
        attribute_file(all_table_data, query)

