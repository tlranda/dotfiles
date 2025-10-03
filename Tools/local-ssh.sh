#!/bin/bash

if [ $# -eq 0 ]; then
    echo "Usage: $0 HOSTNAME";
    exit 0;
fi;

ip_addr=$(${HOME}/./find-local-target.sh $1)
if [[ $? -ne 0 ]]; then
    echo "Unable to find host $1";
    exit 1;
fi
ip_addr=$(echo ${ip_addr} | tail -n1);
ssh ${USER}@${ip_addr};

