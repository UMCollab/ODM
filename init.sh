#!/bin/bash

cd $(readlink -fn $(dirname "$BASH_SOURCE"))

pipenv sync -d
