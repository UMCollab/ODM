#!/bin/bash

hacking_dir=$(readlink -fn $(dirname "$BASH_SOURCE"))
VIRTUAL_ENV_DISABLE_PROMPT=1
. $hacking_dir/bin/python/bin/activate
