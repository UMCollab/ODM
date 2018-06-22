#!/usr/bin/env python

# This file is part of onedrive-magic and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import argparse
import sys

import yaml

from util import onedriveclient

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', help = 'Config file location', default = 'config.yaml')
parser.add_argument('-v', '--verbose', help = 'Enable verbose output', action='store_true')
parser.add_argument('user')

args = parser.parse_args()

with open(args.config, 'r') as configfile:
    config = yaml.safe_load(configfile)

client = onedriveclient.OneDriveClient(config)

drives = client.list_drives(args.user)

items = []
for drive in drives:
    items.append(drive['root'])

expanded = True
while expanded:
    expanded = False
    for item in items:
        if 'folder' in item and 'expanded' not in item:
            items.extend(client.list_folder(item))
            item['expanded'] = True
            expanded = True

if args.verbose:
    yaml.safe_dump(items, sys.stdout)
else:
    for item in items:
        print(item['name'])
