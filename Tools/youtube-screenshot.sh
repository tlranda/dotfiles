#!/bin/bash

# Improved screenshot goes to clipboard AND os
PICTURE="${HOME}/Pictures/Screenshots/yt-$(date).png";
maim -g 1258x710+100+194 -x :0.0 $@ "${PICTURE}" && xclip -selection clipboard -t image/png -i "${PICTURE}";

