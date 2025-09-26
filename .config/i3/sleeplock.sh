#!/bin/bash

# This script picks a lockscreen / sleep background on rotation
# You can initialize its config by running the script directly and can edit
# other settings via this script (run with --help for options)
i3lockcmd=$(python3 ${HOME}/.config/i3/pick_sleep_background.py);
if [[ $? -ne 0 ]]; then
    # USE DEFAULT i3lock (minus unlock UI) to let user know the command failed / check logs
    i3lock -uef &
else
    # Run command with selected desktop background
    eval ${i3lockcmd} &
fi
sleep 1 # Wait 1 second
xset dpms force standby # Force monitors to turn off
wait
