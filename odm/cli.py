#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import argparse
import logging
import sys

import yaml

from kitchen.text.converters import getwriter

from odm import googledriveclient, onedriveclient

class CLI:
    def __init__(self, args, client='microsoft'):
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--config',
            help = 'Config file location',
            default = '/etc/odm.yaml',
        )
        parser.add_argument('-v', '--verbose',
            help = 'Enable verbose output',
            action = 'store_true',
        )
        for arg in args:
            parser.add_argument(arg)

        self.args = parser.parse_args()

        with open(self.args.config, 'r') as configfile:
            self.config = yaml.safe_load(configfile)

        self.config['args'] = self.args

        # Configure root logger
        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter('%(asctime)s %(name)s: %(message)s', '%Y-%m-%dT%H:%M:%S'))
        if self.args.verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        self.logger = logging.getLogger(__name__)

        if client == 'google':
            self.client = googledriveclient.GoogleDriveClient(self.config)
        elif client == 'microsoft':
            self.client = onedriveclient.OneDriveClient(self.config)

    @staticmethod
    def writer_wrap(caller_sys):
        writer = getwriter('utf8')
        caller_sys.stdout = writer(caller_sys.stdout)
        caller_sys.stderr = writer(caller_sys.stderr)