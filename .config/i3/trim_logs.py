import datetime
import os
import pathlib

base_path = pathlib.Path(os.getenv('HOME')) / '.config' / 'i3'
logs = [_ for _ in (base_path / 'logs').iterdir() if _.suffix == '.log']

MAX_KEEP = datetime.timedelta(days=14)

for log in logs:
    with open(log, 'r') as f:
        contents = f.readlines()

    # Scan for errors -- do not purge any logs that have errors
    errors = list()
    cutoff = None
    best_elapsed = None
    now = datetime.datetime.now()
    for line_idx, line in enumerate(contents):
        if 'error' in line.lower():
            errors.append(line_idx)
        date_portion = " ".join(line.split(' ', 2)[:2])
        date_then = datetime.datetime.strptime(date_portion, "%Y-%m-%d %H:%M:%S")
        elapsed = now - date_then
        if elapsed < MAX_KEEP and cutoff is None:
            cutoff = line_idx
            # Don't break, scan for errors all the way through

    # Do not alter logs that have errors so I can find out what they say went wrong
    if len(errors) > 0:
        for error in errors:
            print(f"Found error in log {log} on line {error}! {contents[error].rstrip()}")
        continue

    # Cut out logs that I no longer require
    if cutoff is not None and cutoff > 0:
        print(f"Trimming {cutoff-1} lines from log {log} ({100*(cutoff-1)/len(contents):.2f}%)")
        with open(log, 'w') as f:
            for line in contents[cutoff:]:
                f.write(line)
print(f"All logs handled")

