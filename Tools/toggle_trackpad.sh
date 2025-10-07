#!/bin/bash

# Check current state of trackpad
current_state=$(gsettings get org.gnome.desktop.peripherals.touchpad send-events)

if [ "${current_state}" == "'enabled'" ]; then
    gsettings set org.gnome.desktop.peripherals.touchpad send-events 'disabled'
else
    gsettings set org.gnome.desktop.peripherals.touchpad send-events 'enabled'
fi

