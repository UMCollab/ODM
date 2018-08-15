#!/bin/bash

cd $(readlink -fn $(dirname "$BASH_SOURCE"))

if which virtualenv; then
    [[ -d bin/python/bin ]] || virtualenv bin/python
    . bin/python/bin/activate
    pip install -U pip
    pip install -U -r requirements.txt
else
    echo "Automated environment setup requires virtualenv."
fi
