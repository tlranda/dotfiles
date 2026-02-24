#!/bin/bash

MY_LOCK_LOG="${HOME}/.config/i3/logs/${USER}_pick_sleep_background.log";

# No args? Exit
if [[ $# -eq 0 ]]; then
    echo "SLEEPLOCK.SH SKIPS sleep activation at $(date)" >> ${MY_LOCK_LOG};
    exit;
fi
if [[ "${1}" == "ACTUALLY_LOCK" ]]; then
    echo "SLEEPLOCK.SH invoked: (( ${@} )) at $(date)" >> ${MY_LOCK_LOG};
    shift;
else if [[ "${1}" == "RAM_LOCK" ]]; then
    echo "SLEEPLOCK.sh invoked (( ${@} )) at $(date)" >> ${MY_LOCK_LOG};
fi
fi

# This script picks a lockscreen / sleep background on rotation
# You can initialize its config by running the script directly and can edit
# other settings via this script (run with --help for options)
i3lockcmd=$(python3 ${HOME}/.config/i3/pick_sleep_background.py --overlay-text "${USER}");
if [[ $? -ne 0 ]]; then
    echo "SLEEPLOCK.SH ERROR CODE: $?" >> ${MY_LOCK_LOG};
    echo "SLEEPLOCK.SH RETRIEVED OUTPUT: ${i3lockcmd}" >> ${MY_LOCK_LOG};
    # USE DEFAULT i3lock (minus unlock UI) to let user know the command failed / check logs
    i3lock -uef &
else
    # Run command with selected desktop background
    eval ${i3lockcmd} &
fi
# Pass any argument to sleeplock to prevent it from auto-sleeping displays
if [[ $# -eq 0 ]]; then
    sleep 4 # Wait 4 seconds
    xset dpms force standby # Force monitors to turn off
else if [[ "${1}" == "RAM_LOCK" ]]; then
    # https://www.kernel.org/doc/html/v4.18/admin-guide/pm/sleep-states.html
    # Not allowed on boundedbyte, probably not except root?
    echo mem > /sys/power/state;
fi
fi
wait
