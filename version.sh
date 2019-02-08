#!/bin/bash

cd $(readlink -fn $(dirname "$BASH_SOURCE"))

if [ -d .git ]; then
    git describe --tags | perl -pe 'chomp; s/-/./; s/-.*//' | tee VERSION
elif [ -s VERSION ]; then
    cat VERSION
else
    printf %s UNKNOWN
fi
