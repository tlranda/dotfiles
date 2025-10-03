#!/bin/bash

if [ $# -eq 0 ]; then
    echo "Usage: $0 HOSTNAME";
    exit 0;
fi;

nmap_res=$(nmap -sL 192.168.1.* | grep -e $1);
if [[ "${nmap_res}" == "" ]]; then
    echo "Host '$1' not found";
    exit 1;
fi;
ip_res=$(echo ${nmap_res} | sed "s/.*(\(.*\))/\1/");
echo "Host '$1' found";
echo ${ip_res};

