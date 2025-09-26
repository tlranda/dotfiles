# Dependent modules
import numpy as np

# Builtin modules
import argparse
import datetime
import itertools
import json
import logging
import os
import pathlib
import sys
import time

from collections import OrderedDict

default_base_path = pathlib.Path(os.getenv('HOME')) / '.config' / 'i3'
default_log_path = default_base_path / "logs" / "pick_sleep_background.log",
default_config_path = default_base_path / "sleep_history.json"

# i3lock only supports PNGs
SUPPORTED_FILETYPES = ['.png']
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# IMPORTANT: If errors occur, log them, but do not stdout anything.
# The white default lock screen is a signal to the user that an error occurred
# and they can check the logs for details.

logger = logging.getLogger(__name__)
# I don't allow logging to be configured by argparse so shove it all up here at the top
logconfig = {
        'level': logging.INFO,
        'format': "%(asctime)s %(levelname)s: %(message)s",
        'datefmt': DATETIME_FORMAT
}
if len(sys.argv) == 1:
    # Normal run w/o arguments set
    logging.basicConfig(filename=default_config_path
                        **logconfig)
else:
    # Interactive run should log to stdout and show ALL debug output
    loghandlers = [logging.StreamHandler(sys.stdout)]
    logconfig['level'] = logging.DEBUG
    logging.basicConfig(handlers=loghandlers,
                        **logconfig)

def init_history(configpath):
    if configpath.exists():
        logger.warning(f"Overriding previous history at {configpath}")
        with open(configpath,'r') as f:
            old_history = f.readlines()
        logger.info(f"Overwritten history: {old_history}")
    default = {
            "penalty-weight-multiplier": -1, # If you manually give an image a penalty, multiply it by this value
            "frequency-weight-multiplier": 1, # Increases weight attribution based on access-frequency
            "new-image-weight-advantage": 1, # Increases weight for NEVER picked images
            "base_path": "~/Pictures/", # Where images are located on disk (single directory to search)
            "images": {}, # Stores metadata about historically sampled images
                          # FORMAT:
                          #   Key = filename relative to base_path
                          #   Values:
                          #     last-access: YYYY-MM-DD HH:MM:SS (date of last sampling selection)
                          #     penalty-weight: 0 (manual adjustment to sampling frequency)
                          #     omit: false (manually deny image from being sampled)
            }
    logger.info(f"Initialize NEW history at {configpath}")
    with open(configpath,'w') as f:
        json.dump(default, f)
    return default

def load_history(expect_history):
    if not expect_history.exists():
        logger.info(f"No history / configuration at {expect_history}, initializing as blank")
        # Empty JSON equivalent with reasonable suggestion for default path
        history = init_history()
    else:
        logger.info(f"Loading history / configuration from {expect_history}")
        with open(expect_history, 'r') as jsonf:
            try:
                _history = json.load(jsonf)
            except Exception as e:
                logger.error(f"Failed to load history / configuration file {expect_history} ({type(e)} at {e.lineno}:{e.colno}): {e.msg}")
                exit(1)
            try:
                # Top level key validation
                history = {"penalty-weight-multiplier": _history["penalty-weight-multiplier"],
                           "frequency-weight-multiplier": _history["frequency-weight-multiplier"],
                           "new-image-weight-advantage": _history["new-image-weight-advantage"],
                           "images": _history["images"],
                           "base_path": _history["base_path"],
                           }
            except KeyError as e:
                logger.error(f"History / configuration file does not have required key '{e.args[0]}'. It may be misformatted.")
                exit(1)
            for idx, (key, value) in enumerate(_history['images'].items()):
                # Validate all keys present
                try:
                    for expect_key in ['last-access','penalty-weight','omit']:
                        _ = history['images'][key][expect_key]
                except KeyError:
                    logger.error(f"Image entry for '{key}' lacks expected entry '{expect_key}'")
                    exit(1)
                # Datetimes have to be converted from string
                try:
                    dt_value = datetime.datetime.strptime(value['last-access'], DATETIME_FORMAT)
                except ValueError:
                    logger.error(f"Image entry '{key}' has bad value")
                    exit(1)
                history['images'][key]['last-access'] = dt_value
            # Finished processing from JSON, free the memory
            del _history
    return history

def set_weights(history, base_path):
    keyweights = dict()
    remove_keys = []
    # Index filesystem to validate keys
    for key, value in history['images'].items():
        if (base_path / key).exists():
            weight_adjust = history['penalty-weight-multiplier'] * value['penalty-weight']
            if weight_adjust != 0:
                logger.debug(f"Adjusted base weight for '{key}': {weight_adjust}")
            keyweights[key] = weight_adjust
        else:
            logger.warning(f"Cannot include JSON image key '{key}': FileNotFound")
            remove_keys.append(key)
    # Don't remove keys mid-iteration, remove them afterwards
    for key in remove_keys:
        del history['images'][key]

    # Add any new keys
    original_keyweight_len = len(keyweights)
    added_keys = list()
    for file_path in base_path.iterdir():
        if file_path.suffix.lower() not in SUPPORTED_FILETYPES:
            logger.info(f"Not including file '{file_path}': FileType '{file_path.suffix}' not supported")
            continue
        # Already present file
        if file_path.name in keyweights:
            continue
        # NEW file is given weight == OLDEST + new-image-weight-advantage
        key = file_path.name
        new_weight = history['new-image-weight-advantage']
        logger.debug(f"Initialize NEW image '{key}' with weight {new_weight}")
        keyweights[key] = new_weight
        added_keys.append(key)

    # To make frequency weights matter, we use a quadratic factor of growth
    # (If you apply them linearlly to order of last-accessed, there is no
    # distribution shift! And lots of other curves are simply not dramatic
    # enough or require very precise tuning. Quadratic relationships can be
    # tuned pretty appropriately wrt the length of the list of items with
    # relatively small integer values)

    # Given the parabola (Ax)(-x+B), it always has y-intercept at x=0, y=0
    # The vertex is located at B/2, and its maximum height is described
    # as the function that point
    # We set B/2=|keyweights| and want the max y-height=|keyweights|*frequency-weight-multiplier
    beta = 2*len(keyweights)
    # Which means we are solving for alpha:
    # |keyweights|*frequency-weight-multiplier = (A*|keyweights|)*(-|keyweights|+2*|keyweights|)
    # |keyweights|*frequency-weight-multiplier = (A*|keyweights|)*(|keyweights|)
    # frequency-weight-multiplier = (A*|keyweights|)
    # frequency-weight-multiplier / |keyweights| = A
    alpha = history['frequency-weight-multiplier'] / len(keyweights)
    apex = (alpha*len(keyweights))*(-1*alpha+2*len(keyweights))
    # Postmortem update extra weights based on max quadratic added factor + configured weight adjustment for new image
    newkey_weight_update = apex
    if newkey_weight_update > 0:
        for key in added_keys:
            logger.debug(f"Fix NEW image keyweight for '{key}' by adding weight {newkey_weight_update}")
            keyweights[key] += newkey_weight_update

    # Sort last-access oldest->newest as linear weight to prioritize OLD
    inv_lkeys = list([v['last-access'] for v in history['images'].values()])
    inv_kkeys = list(history['images'].keys())
    key_sort = np.argsort(inv_lkeys)
    for idx, key_idx in enumerate(reversed(key_sort)):
        key = inv_lkeys[key_idx]
        keyweight_key = inv_kkeys[key_idx]
        if keyweight_key not in keyweights:
            # I don't think this should be able to happen, but don't allow it
            logger.error(f"History includes unkonwn key: '{key}'")
            exit(1)

        # Plug into quadratic formula to get extra weight from frequency
        # x = idx
        extra_weight = (alpha*idx)*(-1*alpha+beta)

        logger.debug(f"Add weight {extra_weight} to key '{keyweight_key}' based on last-access {key}")
        keyweights[keyweight_key] += extra_weight

    # Build ordered dict to priortize least-hated but oldest ones
    hist_sort = OrderedDict()
    inv_wkeys = list(keyweights.values())
    inv_kkeys = list(keyweights.keys())
    weightsort = np.argsort(inv_wkeys)
    for value_idx in reversed(weightsort):
        value = inv_wkeys[value_idx]
        # Really negative values should not be pickable
        if value < 0:
            logger.info(f"Drop key {inv_kkeys[value_idx]} for negative weight: {value}")
            continue
        logger.debug(f"Set weight for key '{inv_kkeys[value_idx]}' = {value}")
        hist_sort[inv_kkeys[value_idx]] = value

    # Filter hard omits out
    for key, value in history['images'].items():
        if value['omit'] and key in hist_sort:
            logger.info(f"Omit key '{key}' due to hard-omit flag")
            del hist_sort[key]

    return history, hist_sort

def new_history_for_image():
    return {
            "last-access": datetime.datetime.now().strftime(DATETIME_FORMAT),
            "penalty-weight": 0,
            "omit": False,
            }

def update_last_access(history, selected_key, config):
    # Ensure JSON-serializability
    for image in history['images']:
        history['images'][image]['last-access'] = history['images'][image]['last-access'].strftime(DATETIME_FORMAT)
    # Update last-access
    if selected_key not in history['images']:
        history['images'][selected_key] = new_history_for_image()
    else:
        history['images'][selected_key]['last-access'] = datetime.datetime.now().strftime(DATETIME_FORMAT)
    with open(config, 'w') as f:
        logger.info(f"Update config {config} with latest selection and metadata")
        logger.debug(history)
        json.dump(history, f)

def make_weighted_choice(hist_sort):
    rng = np.random.default_rng()
    weightsum = sum(hist_sort.values())
    logger.info(f"Available keys and weights for selection: {hist_sort} (Sum weight: {weightsum})")
    init_choice = choice = rng.integers(0,weightsum)
    keys = list(hist_sort.keys())
    key_idx = 0
    while choice > hist_sort[keys[key_idx]]:
        choice -= hist_sort[keys[key_idx]]
        key_idx += 1
    selected_key = keys[key_idx]
    logger.info(f"Random integer {init_choice} selects key '{selected_key}'")
    return selected_key


# COMMANDLINE PARSING

def build():
    dhelp = "(Default: %(default)s)"
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=pathlib.Path, default=default_config_path,
                        help=f"JSON configuration file to use {dhelp}")
    #           + Initializing a BLANK history JSON at given base_path / other options
    parser.add_argument('--init', action='store_true',
                        help=f"Create new JSON at --config path {dhelp}")
    #           + Adjusting baseline configuration
    parser.add_argument('--keys-adjust', nargs="*", default=None, action='append',
                        help=f"List of TOP-LEVEL keys to adjust in config")
    parser.add_argument('--values-adjust', nargs="*", default=None, action='append',
                        help=f"List of TOP-LEVEL values to adjust in config")
    #           + Forcing images to be indexed into history (sets last-access etc)
    parser.add_argument('--index', type=pathlib.Path, default=None, nargs="*", action='append',
                        help=f"Index images (relative to base path; touch its last-access / initialize its config entry)")
    #           + Adjusting the penalty weight of an image / other config
    parser.add_argument('--penalize-images', type=pathlib.Path, nargs="*", default=None,
                        action='append', help=f"Images to set individual penalty weights for")
    parser.add_argument('--penalize-weights', type=int, nargs="*", default=None, action='append',
                        help=f"Penalty weights per image in --penalize-images")
    #           + Forcing an image to be omitted/un-omitted
    parser.add_argument('--image-toggle-omit', nargs="*", default=None, action='append',
                        help=f"Images to forcibly omit (or un-omit) from selection")
    #           + Validating JSON history as runnable
    parser.add_argument('--parse', action='store_true',
                        help=f"Parse JSON at --config path to ensure it has no errors {dhelp}")
    parser.add_argument('--parse-with-weights', action='store_true',
                        help=f"Parse JSON at --config path and show resulting weights {dhelp}")
    return parser

def flatten_arg(attr):
    return list(itertools.chain.from_iterable(attr))

def require_simultaneously_set_and_equal_length(args, *argnames):
    attrs = [getattr(args, name) for name in argnames]
    if all([_ is None for _ in attrs]) or all([len(_) == 0 for _ in attrs]):
        # All empty -- OK
        return
    if None in attrs or 0 in map(len, attrs)):
        raise ValueError(f"Must give EQUAL number of arguments to all paired arguments: {', '.join(argnames)}")

    # Flatten multiple arg groups in order they are given
    for name, attr in zip(argnames, attrs):
        setattr(args, name, flatten_arg(attr))
    attrs = [getattr(args, name) for name in argnames]
    lengths = set(list(map(len, attrs)))
    if len(lengths) > 1:
        raise ValueError(f"Must give EQUAL number of arguments to all paired arguments: {', '.join(argnames)}")

def parse(args=None, prs=None):
    if prs is None:
        prs = build()
    if args is None:
        args = prs.parse_args()

    # Validation
    require_simultaneously_set_and_equal_length(args, 'keys_adjust','values_adjust')
    if args.keys_adjust is not None or args.values_adjust is not None:
        type_map = {
                'penalty-weight-multiplier': int,
                'frequency-weight-multiplier': int,
                'new-image-weight-advantage': float,
                'base_path': str,
                }
        args.top_level_config_edits = dict((k,type_map[k](v)) for (k,v) in zip(args.keys_adjust, args.values_adjust))
    else:
        args.top_level_config_edits = None

    if args.index is not None:
        # Have to be relative to config's base path -- FileNotFoundError later if not found
        args.index = list(itertools.chain.from_iterable(args.index))

    require_simultaneously_set_and_equal_length(args, 'penalize_images','penalize_weights')
    if args.penalize_images is not None or args.penalize_weights is not None:
        args.image_penalties = dict((k,v) for (k,v) in zip(args.penalize_images, args.penalize_weights))
    else:
        args.image_penalties = None

    if args.image_toggle_omit is not None:
        args.image_toggle_omit = list(itertools.chain.from_iterable(args.image_toggle_omit))

    return args

if __name__ == '__main__':
    args = parse()

    # User requests new config file
    if args.init:
        init_history(args.config)

    # Load config
    history = load_history(args.config)

    # User adjustments to config
    if args.top_level_config_edits is not None:
        for (k,v) in args.top_level_config_edits.items():
            if k not in history:
                logger.info(f"Add new configuration key {k} with value {v}")
            else:
                logger.info(f"Override configuration key {k} (former value: {history[k]}) with new value {v}")
            if k == 'base_path':
                logger.warning(f"Overriding base_path may invalidate image paths unless all images formerly indexed at {history[k]} can be located at {v}")
                logger.info(f"Current indexed images at {history[k]} are: {', '.join(history['images'].keys()) if len(history['images']) > 0 else 'N/A'}")
            history[k] = v

    # Properly set config_base_path
    # If '~' is in the path, you have to do ugly things
    parts = list(pathlib.Path(history['base_path']).parts)
    if parts[0] == '~':
        parts[0] = pathlib.Path.home()
    if len(parts) > 1:
        for part in parts[1:]:
            parts[0] = parts[0].joinpath(part)
    config_base_path = parts[0]

    # User requests one or more images to be indexed into history
    if args.index is not None:
        for idx, image in enumerate(args.index):
            if not (config_base_path / image).exists():
                raise FileNotFoundError(f"Could not locate image {image} at {config_base_path}")
            history['images'][image] = new_history_for_image()
            if idx < len(args.index)-1:
                logger.debug("Sleep 1s to maintain separate last-access timings")
                time.sleep(1)

    # User requests penalty adjustments
    if args.image_penalties is not None:
        for image, penalty in args.image_penalties.items():
            if image not in history['images']:
                raise ValueError(f"Image {image} is not indexed in configuration history {args.config}")
            history['images'][image]['penalty-weight'] = penalty

    # User requests omission adjustments
    if args.image_toggle_omit is not None:
        for image in args.image_toggle_omit:
            if image not in history['images']:
                raise ValueError(f"Image {image} is not indexed in configuration history {args.config}")
            history['images'][image]['omit'] = not history['images'][image]['omit']

    # ALL CMDLINE EDITS OVER
    if args.parse:
        import pprint
        pprint.pprint(history)
        exit(0)

    history, hist_sort = set_weights(history, config_base_path)
    if args.parse_with_weights:
        import pprint
        pprint.pprint(history)
        pprint.pprint(hist_sort)
        exit(0)

    # Make weighted choice
    selected_key = make_weighted_choice(hist_sort)
    update_last_access(history, selected_key, args.config)

    # Form command for output
    basic_path = config_base_path.joinpath(selected_key)
    escaped_path = f'"{basic_path}"'
    command = ['i3lock', '-utfe', '-i', escaped_path]
    # For whatever reason, directly calling subprocess doesn't work even with shell=True and other considerations (typically related to spaces in the file path).
    # However, we're wrapping this script in a shell script anyways that can eval this / fall back in the event we returned nonzero value due to any errors we catch above
    # This also means if I failed to catch an exception, we won't attempt to eval a stacktrace
    print(' '.join(command))

