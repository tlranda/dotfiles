import copy
import datetime
import json
import logging
import os
import pathlib
import subprocess

logger = logging.getLogger(__name__)

base_path = pathlib.Path(os.getenv('HOME')) / '.config' / 'i3'
config_path = base_path / "settings.json"

DATETIME_FORMAT='%Y-%m-%d %H:%M:%S'

# Original dmenu_run is a bash script a la:
# dmenu_path | dmenu "${@}" | ${SHELL:-"/bin/sh"} &

def update_dmenu_settings(fname, fpath):
    with open(fpath,'r') as f:
        lines = f.readlines()
    injections = list()
    # Filter to relevant lines
    for line in lines:
        if line.startswith('alias'):
            addition = line.split('=')[0][len('alias '):]
            injections.append(addition)
        if not (line.startswith(' ') or line.startswith('#')) and '()' in line:
            addition = line.split('(')[0]
            injections.append(addition)
    return injections

def populate_options():
    # Get user's choice but allow intercepting it prior to fork for extra directives
    # Pass in my os.environ to hopefully include directories I add to PATH
    if 'dmenu_path_addition' in settings:
        existing_path = os.environ["PATH"]
        for name in settings['dmenu_path_addition']:
            parts = list(pathlib.Path(name).parts)
            if parts[0] == '~':
                parts[0] = os.environ["HOME"]
            if len(parts) > 1:
                name = pathlib.Path(parts[0]).joinpath(*parts[1:])
            else:
                name = parts[0]
            if str(name) not in existing_path:
                existing_path += f":{name}"
        os.environ["PATH"] = existing_path
    dmenu_path = subprocess.Popen(("dmenu_path"), stdout=subprocess.PIPE, env=os.environ)
    dmenu_choices = dmenu_path.stdout

    dmenu_choices = [_.decode('utf-8') for _ in dmenu_choices.readlines()]

    # Injection from settings
    # NOTE: You have to manually delete the dmenu_path cache file and run in your own terminal (with updated PATH) to refresh any directories indicated by PATH
    save_settings = False
    if 'dmenu_injection' in settings:
        for fname in settings['dmenu_injection']:
            local_settings = settings['dmenu_injection'][fname]
            # Load filename with ~ substitution
            parts = list(pathlib.Path(fname).parts)
            if parts[0] == '~':
                parts[0] = pathlib.Path.home()
            fpath = parts[0].joinpath(*parts[1:])
            # Retrieve record for last-modified
            try:
                last_modified = datetime.datetime.fromtimestamp(os.stat(fpath).st_mtime)
            except:
                logger.error(f"Could not retrieve modified time for '{fpath}'")
                continue
            last_recorded = datetime.datetime.strptime(local_settings['last-modified'], DATETIME_FORMAT)
            # Update needed
            if last_modified > last_recorded:
                logger.info(f"Updating dmenu injection for '{fname}' (OLD: {local_settings})")
                local_settings['names'] = update_dmenu_settings(fname, fpath)
                local_settings['last-modified'] = datetime.datetime.now().strftime(DATETIME_FORMAT)
                logger.info(f"New settings: {local_settings['names']}")
                save_settings = True
            # Don't dupe
            for new_name in local_settings['names']:
                if new_name in local_settings['non-import']:
                    logger.debug(f"Skip name '{new_name}' -- non-importable")
                    continue
                new_name += "\n"
                if new_name in dmenu_choices:
                    logger.debug(f"Skip name '{new_name.rstrip()}' -- already present")
                    continue
                logger.info(f"Inject name '{new_name.rstrip()}' from '{fname}'")
                dmenu_choices.append(new_name)

    # Remove any remove-list items
    print("".join(dmenu_choices))
    if 'dmenu_remove' in settings:
        logger.debug(f"Removing entries from dmenu choices based on settings['dmenu_remove']: {settings['dmenu_remove']}")
        for entry in settings['dmenu_remove']:
            entry_ = entry+'\n'
            if entry_ in dmenu_choices:
                dmenu_choices.remove(entry_)

    # Let's try recency bias first (no timestamps, just order of usage)
    if 'dmenu_recency' in settings:
        reinclude = list()
        for entry in settings['dmenu_recency']:
            entry_ = entry+'\n'
            if entry_ in dmenu_choices:
                reinclude.append(entry_)
                dmenu_choices.remove(entry_)
            # Could tidy up settings['dmenu_recency'] if you want to, but I think not for now
        logger.debug(f"Promote names ({reinclude}) due to recency")
        dmenu_choices = reinclude + dmenu_choices

    # TODO: Add history of selections to prioritize most-recent/frequent prefix
    # You can pipe a whole bunch of things together to get priority sorting into dmenu once you track choices
    # echo this list (as "#used, item" pairs) into:
    #    sort -r (invert order)
    #    awk '{printf("%d %s\n", $1 * FREQUENCY_WEIGHT + NR, $2)}' (add list-order as tiebreaker, but multiply usage amount as 1M in aario/dmenu -- I think FREQ_WEIGHT >= len(list) is sufficient
    #    sort -n -r (un-invert order but sort numerically based on weight key)
    #    awk '{print $NF}' (print just the items, now in sorted order)
    #
    # Dmenu will preserve the sorting order as it prunes items down
    # Join
    dmenu_choices = "".join(dmenu_choices)

    if save_settings:
        with open(config_path, 'w') as f:
            json.dump(settings, f, indent=1)

    choice = subprocess.check_output(("dmenu"), input=dmenu_choices, text=True).rstrip()
    return choice

def process_choice(choice):
    # Default everything to None
    program = recency_program = args = signal = None

    # Regex doesn't do the split the way I want, so implement my own split here
    arg_split = None
    signal_split = None
    if '@' in choice:
        # format: @<#> to specify workspace
        signal_split = choice.index('@')
    if ':' in choice:
        # format: :<args> to give program arguments
        arg_split = choice.index(':')

    if arg_split is not None and signal_split is not None:
        if arg_split < signal_split:
            program = choice[:arg_split]
            args =    choice[arg_split+1:signal_split]
            signal =  choice[signal_split+1:]
        else:
            program = choice[:signal_split]
            signal =  choice[signal_split+1:arg_split]
            args =    choice[arg_split+1:]
    elif signal_split is not None:
        program = choice[:signal_split]
        signal =  choice[signal_split+1:]
    elif arg_split is not None:
        program = choice[:arg_split]
        args =    choice[arg_split+1:]
    else:
        program = choice

    recency_program = program

    if args is not None:
        args = args.split(' ')

    # Some programs need to be executed within a terminal for you to observe what happens
    if 'requires_terminal' in settings and program in settings['requires_terminal']:
        args = "'"+" ".join(args)+"'"
        if args is None:
            _args = copy.copy(settings['terminal_args'])
            if 'terminal_preuser_args' in settings:
                _args += [settings['terminal_preuser_args']]
                _args[-1] += program
            else:
                _args += [program]
            args = _args
        else:
            _args = copy.copy(settings['terminal_args'])
            if 'terminal_preuser_args' in settings:
                _args += [settings['terminal_preuser_args']+program+" "+args]
            else:
                _args += [program+" "+args]
            args = _args
        if 'terminal_postuser_args' in settings:
            args[-1] += settings['terminal_postuser_args']
        program = settings['terminal']
        logger.debug(f"Prepare shell command due to requiring terminal: {args}")

    # Tidy up with validation
    if signal is not None:
        try:
            signal_int = int(signal)
            # Space-pad to properly fill in i3-msg
            signal = f" {signal}"
        except ValueError:
            logger.error(f"Could not convert indicated monitor signal (via @) '{signal}' to integer")
            signal = ""

    logger.debug(f"Dmenu selects program '{program}' with monitor signal value '{signal}' and arguments '{args}'")
    return signal, program, recency_program, args

def launch(signal, program, recency_program, args):
    # Send message to automanager via tick
    if signal is not None:
        automanager_signal = f"automanager::force_workspace{signal}"
        logger.debug(f"Send signal '{automanager_signal}' to automanager")
        status = subprocess.run(("i3-msg", "-t", "send_tick", automanager_signal))
        if status.returncode != 0:
            logger.error(status.returncode)
    # Update recency settings
    if 'dmenu_recency' not in settings:
        settings['dmenu_recency'] = list()
    if recency_program in settings['dmenu_recency']:
        settings['dmenu_recency'].remove(recency_program)
    settings['dmenu_recency'].insert(0,recency_program)
    with open(config_path, 'w') as f:
        json.dump(settings, f, indent=1)

    # Form program with arguments
    if args is not None:
        program = [program]
        program.extend(args)
    # Run program as expected and exit this process
    logger.info(f"Launch program '{program}'")
    proc = subprocess.Popen(program)
    # If these aren't the same, it's a terminal that will execvp or something;
    # You can only detach if you own the process ID created by the program!
    if program == recency_program:
        proc.detach()

if __name__ == '__main__':
    global settings

    logging.basicConfig(filename=base_path / "logs" / "special_dmenu_handler.log",
                        level=logging.DEBUG,
                        format="%(asctime)s %(levelname)s: %(message)s",
                        datefmt=DATETIME_FORMAT)
    # Fetch settings
    logger.info(f"Fetch configuration from '{config_path}'")
    with open(config_path,"r") as f:
        settings = json.load(f)
    logger.info(f"Settings loaded: {settings}")
    if 'clear_dmenu_cache' in settings and settings['clear_dmenu_cache']:
        cached_path = pathlib.Path(os.environ['HOME']).joinpath('.cache','dmenu_run')
        try:
            cached_path.unlink()
            logger.info(f"Cleared dmenu_path cache at '{cache_path}'")
        except:
            logger.error(f"Tried to unlink dmenu_path cache at '{cached_path}', but failed")

    launch(*process_choice(populate_options()))

