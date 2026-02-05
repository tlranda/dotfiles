#!/bin/bash

# This script picks a lockscreen / sleep background on rotation
# You can initialize its config by running the script directly and can edit
# other settings via this script (run with --help for options)
i3lockcmd=$(python3 ${HOME}/.config/i3/pick_sleep_background.py --overlay-text "${USER}");
if [[ $? -ne 0 ]]; then
    echo "SLEEPLOCK.SH ERROR CODE: $?" >> ${HOME}/.config/i3/logs/pick_sleep_background.log;
    echo "SLEEPLOCK.SH RETRIEVED OUTPUT: ${i3lockcmd}" >> ${HOME}/.config/i3/logs/pick_sleep_background.log;
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
fi
wait
