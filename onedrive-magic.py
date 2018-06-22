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
parser.add_argument('user')

args = parser.parse_args()

with open(args.config, 'r') as configfile:
    config = yaml.safe_load(configfile)

yaml.dump(config, sys.stdout)

client = onedriveclient.OneDriveClient(config)

print(client.token)

for drive in client.get('users/{0}@{1}/drives'.format(args.user, config['domain']))['value']:
    #drives/{0}/root?expand=children(select=id,name)
    yaml.safe_dump(client.get('drives/{0}/root?expand=children'.format(drive['id'])), sys.stdout)
