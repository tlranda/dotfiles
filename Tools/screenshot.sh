#!/bin/bash

# Improved screenshot goes to clipboard AND os
PICTURE="${HOME}/Pictures/Screenshots/$(date).png";
maim $@ "${PICTURE}" && xclip -selection clipboard -t image/png -i "${PICTURE}";

