#!/bin/sh
xrandr --output DisplayPort-0 --primary --mode 1920x1080 --pos 0x0 --rotate normal;
if [[ $? -ne 0 ]]; then
    echo "Error for DisplayPort-0";
fi
xrandr --output DisplayPort-1 --mode 1920x1080 --pos 0x1080 --rotate inverted;
if [[ $? -ne 0 ]]; then
    echo "Error for DisplayPort-1";
fi
xrandr --output DisplayPort-2 --off;
xrandr --output HDMI-A-0 --mode 1920x1080 --pos 1920x0 --rotate normal;
if [[ $? -ne 0 ]]; then
    echo "Error for HDMI-A-0";
fi
