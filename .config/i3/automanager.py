#!/usr/bin/env python3

import i3ipc

import json
import os
import pathlib
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

i3 = i3ipc.Connection()

def auto_assign_new_to_workspace(i3, e):
    """
        Smarter way to auto-configure certain applications to open in particular
        workspaces (when user-defined). They can still be moved elsewhere
        after the fact if desired

        If settings['ticks']['force_workspace'] exists and has integer/None,
        force the window to open in that workspace/no particular workspace
        instead
    """
    remaps = defaultdict(type(None), settings['app_force_workspace'])

    # Learn the class of what just opened
    container_class = e.ipc_data['container']['window_properties']['class']
    remap_container_class = container_class
    # Special case for steam apps that aren't given a specific override
    if remap_container_class.startswith('steam_app_') and not remaps[remap_container_class]:
        remap_container_class = 'steam_app_'
    # Default remapping ONLY applies to first window of given class
    ws_target = None
    if len(i3.get_tree().find_classed(container_class)) < 2:
        ws_target = remaps[remap_container_class]
    if 'no_default' in settings['ticks']:
        ws_target = None
        # Clear the signal
        del settings['ticks']['no_default']
    logger.debug(f"Seeking container-workspace mapping for container {container_class} and target {ws_target}")

    # Determine if mapped class or not
    if ws_target is not None:
        # Determine workspace name (it may be renamed)
        try:
            for ws in i3.get_tree().workspaces():
                # Always parse names correctly by number
                if ':' not in ws.name:
                    ws_num = int(ws.name)
                else:
                    ws_num = int(ws.name.split(':',1)[0])
                logger.debug(f"Inspect workspace {ws.name} as {ws_num}")

                # Found the workspace to use
                if ws_num == ws_target:
                    logger.info(f"New container <class='{container_class}'> targets window {ws_target} as name '{ws.name}'.")
                    # BUG: If an application is slow-to-launch or does pre-launch stuff that takes nontrivial time, this OFTEN moves the previously active window to the workspace!
                    # Possible solutions:
                    # 1) Ignore-once for discord/etc so it hooks the REAL opening?
                    # 2) Sleep a bit on these apps to wait for real initialization?
                    # 3) Can the command below target specific container?
                    command = f'move container to workspace "{ws.name}"'
                    status = i3.command(command)
                    if not status[0].success:
                        logger.error(status[0].error)
                        return
                    # Follow the workspace with focus -- if it wasn't active, it is now
                    logger.info(f"Change focus to workspace '{ws.name}'")
                    command = f'workspace "{ws.name}"'
                    status = i3.command(command)
                    if not status[0].success:
                        logger.error(status[0].error)
                        return
                    # Halt processing this function
                    return
            logger.info(f"New container <class='{container_class}'> targets NEW window {ws_target}. Create it.")
            # Workspace does not currently exist, but you can create it
            # You don't need to invoke rename(), it will get called naturally
            command = f'move container to workspace "{ws_target}"'
            status = i3.command(command)
            if not status[0].success:
                logger.error(status[0].error)
                return
        except:
            # Don't crash my script but help me debug it
            logger.error(f"{type(e)} Exception during auto_assign_new_to_workspace()")
            try:
                logger.error(e.msg)
            except:
                return
    else:
        logger.debug(f"New container <class='{container_class}'> has no specialized target.")
        #logger.debug("Called rename() due to new container (via auto_assign_new_to_workspace())")
        e.change += " (via auto_assign_new_to_workspace())"
        # Just update the name of the workspace as needed
        rename(i3, e)

class AutoCapitalizeDictionary(dict):
    """
        Similar to a defaultdict, but I need to operate on the missing key itself
        So we just do a similar thing and override the __missing__() function
    """
    def __missing__(self, key):
        # We don't know how to make these keys, don't fix them but raise a regular KeyError
        if (not hasattr(key,'capitalize')) or (not callable(getattr(key,'capitalize'))):
            raise KeyError(key)
        self[key] = key.capitalize()
        return self[key]

def rename(i3, e):
    """
        Rename the workspace so number-addressing still works but the app names
        are provided.
        Uses configured values to nice-ify names, otherwise just capitalize it.
    """
    logger.debug(f"Called rename() due to {e.change} trigger")
    renames = AutoCapitalizeDictionary(settings['app_rename'])
    # I3 handle iterates over workspaces
    for i in i3.get_tree().workspaces():
        # The leaves in a workspace are its containers
        mergename = " | ".join([renames[_.window_class] for _ in i.leaves()])
        proposename = "" if mergename == "" else f"{i.num}: {mergename}"

        # No action required
        if i.name == proposename:
            continue
        # Final window exits, revert to just number
        elif proposename == "":
            if str(i.num) == i.name:
                continue
            logger.info(f"Rename workspace {i.name} --> {i.num}")
            status = i3.command(f'rename workspace "{i.name}" to "{i.num}"')
            if not status[0].success:
                logger.error(status[0].error)
            continue
        # Use newly formed name
        logger.info(f"Rename workspace {i.name} --> {proposename}")
        status = i3.command(f'rename workspace "{i.name}" to "{proposename}"')
        if not status[0].success:
            logger.error(status[0].error)

def tick_listener(i3, e):
    """
        Allows i3-msg to intercept tick messages to produce or alter behaviors
        Format: i3-msg -t send_tick "automanager::<TRIGGER> <VALUE_PAYLOAD>"

        Accepted ticks will be placed into the settings['ticks'] dictionary
        and should be unset upon consumption.
    """
    # Search message to see if it's one that we respond to
    listen_identifier = "automanager::"
    if not e.payload.startswith(listen_identifier):
        logger.debug(f"Ignore non-automanager-scoped tick: {e.payload}")
        return
    trim_payload = e.payload[len(listen_identifier):]
    if ' ' in trim_payload:
        trigger, value = trim_payload.split(' ',1)
    else:
        trigger = trim_payload
        value = None
    settings['ticks'][trigger] = value
    logger.info(f"Tick registered for trigger '{trigger}' with value '{value}'")

def main():
    global settings

    base_path = pathlib.Path(os.getenv('HOME')) / '.config' / 'i3'
    logging.basicConfig(filename=base_path / "logs" / "automanager.log",
                        level=logging.DEBUG,
                        format="%(asctime)s %(levelname)s: %(message)s",
                        datefmt='%Y-%m-%d %H:%M:%S')
    config_path = base_path / "settings.json"
    logger.info(f"Fetch configuration from '{config_path}'")
    with open(config_path,"r") as f:
        settings = json.load(f)
    # Inject tick-based overrides -- non-writable portion of JSON
    settings['ticks'] = dict()
    logger.info(f"Settings loaded: {settings}")

    # Subscribe to events
    i3.on("window::new", auto_assign_new_to_workspace)
    i3.on("window::move", rename)
    #i3.on("window::title", rename) # DISABLE -- no window titles seem to actually matter for this, maybe related to i3 hangs?
    i3.on("window::close", rename)
    i3.on("tick", tick_listener)

    i3.main()


if __name__ == "__main__":
    main()

