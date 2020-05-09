#!/bin/bash

hacking_dir=$(readlink -fn $(dirname "$BASH_SOURCE"))
cd $hacking_dir
pipenv run pip install -e .
alias bm='pipenv run bm'
alias gdm='pipenv run gdm'
alias odm='pipenv run odm'
