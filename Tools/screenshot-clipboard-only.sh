#!/bin/bash

# Improved screenshot goes to clipboard AND os
maim $@ | xclip -selection clipboard -t image/png;

