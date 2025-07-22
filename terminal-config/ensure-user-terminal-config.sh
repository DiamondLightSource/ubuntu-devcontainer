#!/bin/bash
set -e

# If the files aren't in the user's terminal config then copy from the template
mkdir -p $USER_TERMINAL_CONFIG
for file in bashrc inputrc zshrc; do
    if [ ! -f $USER_TERMINAL_CONFIG/$file ]; then
        cp /root/terminal-config/$file-template $USER_TERMINAL_CONFIG/$file
    fi
done
