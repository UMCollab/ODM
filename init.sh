#!/bin/bash

cd $(readlink -fn $(dirname "$BASH_SOURCE"))

virtualenv bin/python
. bin/python/bin/activate
pip install -U pip
pip install -I -r requirements.txt
