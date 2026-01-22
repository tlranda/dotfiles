#!/bin/bash

# USAGE: ./overlay_username.sh {input_image} {output_image} {label}
# input_image defaults to 'base.png'
# output_image defaults to 'output.png'
# label defaults to '${USER}'

# Configurable parts of the script
FONT="/usr/share/fonts/truetype/UbuntuMono/UbuntuMonoNerdFontMono-Bold.ttf";
FONTSIZE="72";
BORDER="10x10";

# Argument parsing
LABEL="${USER}";
input_image="base.png";
if [[ $# -ge 1 ]]; then
    input_image="$1";
fi;
output_image="output.png";
if [[ $# -ge 2 ]]; then
    output_image="$2";
fi;
if [[ $# -gt 2 ]]; then
    shift 2;
    LABEL="${@}";
fi;


# Figure out room needed for text first -- python script caches info!
SIZE=$(python3 track_sizes.py "${LABEL}");
# Do the actual overlay
convert ${input_image} \
    \( -background none \
       -fill white \
       -font ${FONT} \
       -pointsize ${FONTSIZE} label:"${LABEL}" \
       -trim +repage \
       -bordercolor none \
       -border ${BORDER} \
       -alpha set \
       -channel A \
       -evaluate set 0 +channel \
       -fill "rgba(0,0,0,0.6)" \
       -draw "roundrectangle 0,0 ${SIZE} 10,10" \
       -blur 0x3 \) \
    -gravity center \
    -compose over \
    -composite \
    -font ${FONT} \
    -pointsize ${FONTSIZE} \
    -fill white \
    -gravity center \
    -annotate +0+0 "${LABEL}" \
    ${output_image}

