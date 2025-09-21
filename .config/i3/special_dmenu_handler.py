import subprocess
import os
import pathlib
import logging

logger = logging.getLogger(__name__)

base_path = pathlib.Path(os.getenv('HOME')) / '.config' / 'i3'
logging.basicConfig(filename=base_path / "logs" / "special_dmenu_handler.log",
                    level=logging.DEBUG,
                    format="%(asctime)s %(levelname)s: %(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S')

# Original dmenu_run is a bash script a la:
# dmenu_path | dmenu "${@}" | ${SHELL:-"/bin/sh"} &

# Get user's choice but allow intercepting it prior to fork for extra directives
dmenu_path = subprocess.Popen(("dmenu_path"), stdout=subprocess.PIPE)
choice = subprocess.check_output(("dmenu"), stdin=dmenu_path.stdout).decode('utf-8').rstrip()

# Look for colon at the end of program name to signify a workspace identifier
if ':' not in choice:
    monitor_signal = None
    program = choice
else:
    program, monitor_signal = choice.rsplit(':',1)
    if monitor_signal != "":
        monitor_signal = " "+monitor_signal
logger.debug(f"Dmenu selects program '{program}' with monitor signal value '{monitor_signal}'")

# Send message to automanager via tick
if monitor_signal is not None:
    status = subprocess.run(("i3-msg", "-t", "send_tick", f"automanager::force_workspace{monitor_signal}"))
    if status.returncode != 0:
        logger.error(status.returncode)

# Run program as expected and exit this process
subprocess.Popen(program, shell=True).detach()

