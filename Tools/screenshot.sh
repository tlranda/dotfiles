#!/bin/bash

# Improved screenshot goes to clipboard AND os
local PICTURE="${HOME}/Pictures/Screenshots/$(date).png";
maim $@ "${PICTURE}" && xclip -selection clipboard -t image/png -i "${PICTURE}";

