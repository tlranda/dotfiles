#!/bin/bash

user_prepend="{\"name\":\"user\",\"markup\":\"none\",\"full_text\":\" ${USER} \"},";
first=1;
i3status --config ~/.config/i3/i3status.conf | while :
do
    read line;
    if [[ "${line}" == "{\"version\":"* ]]; then
        echo "${line}" || exit 1;
        continue;
    fi;
    if [[ "${line}" == "[" ]]; then
        echo "${line}" || exit 1;
        continue;
    fi;
    if [[ ${first} -eq 1 ]]; then
        echo "[${user_prepend}${line#[}" || exit 1;
        first=0;
    else
        echo ",[${user_prepend}${line#,[}" || exit 1;
    fi;
done;
