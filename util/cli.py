#!/usr/bin/env python

# This file is part of onedrive-magic and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import argparse
import sys

import yaml

from util import onedriveclient

class CLI(object):
    def __init__(self, positional_args):
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--config', help = 'Config file location', default = 'config.yaml')
        parser.add_argument('-v', '--verbose', help = 'Enable verbose output', action='store_true')
        for arg in positional_args:
            parser.add_argument(arg)

        self.args = parser.parse_args()

        with open(self.args.config, 'r') as configfile:
            self.config = yaml.safe_load(configfile)

        self.client = onedriveclient.OneDriveClient(self.config)
