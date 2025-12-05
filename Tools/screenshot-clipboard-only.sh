#!/bin/bash

# Improved screenshot goes to clipboard AND os
PICTURE="/tmp/clipboard_screenshot.png";
maim $@ "${PICTURE}" && xclip -selection clipboard -t image/png -i "${PICTURE}";
# Show screenshot in dunst notification
dunstify -I "${PICTURE}" -a "Screenshot" "Screenshot in Clipboard!";
rm -f "${PICTURE}";

