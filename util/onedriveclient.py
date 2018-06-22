#!/usr/bin/env python

# This file is part of onedrive-magic and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import re
import requests
import sys
import time

import json

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

class OneDriveClient(object):
    def __init__(self, config):
        self.baseurl = 'https://graph.microsoft.com/v1.0/'
        self.config = config
        client = BackendApplicationClient(client_id = config.get('client_id'))
        self.msgraph = OAuth2Session(client = client)
        self._get_token()

    def _get_token(self):
        self.token = self.msgraph.fetch_token(
            token_url = 'https://login.microsoftonline.com/{0}/oauth2/v2.0/token'.format(self.config.get('domain')),
            client_id = self.config.get('client_id'),
            client_secret = self.config.get('client_secret'),
            scope = [ 'https://graph.microsoft.com/.default' ],
        )

    def _get(self, path):
        if self.token['expires_at'] > time.time():
            self._get_token()

        return self.msgraph.get(
            '{0}{1}'.format(self.baseurl, path),
            timeout = self.config.get('timeout', 5),
            allow_redirects = False,
        )

    def get(self, path):
        result = None
        while not result:
            result = self._get(path)
            if result.status_code == 429:
                delay = result.headers['retry-after']
                result = None
                print('Throttled, sleeping for {0} seconds'.format(delay))
                time.sleep(delay)
            else:
                result.raise_for_status()

        if result.status_code == 302:
            return { 'location': result.headers['location'] }
        else:
            return json.loads(result.content)

    def list_drives(self, user):
        drives = self.get('users/{0}@{1}/drives'.format(user, self.config['domain']))['value']
        for d in drives:
            d['root'] = self.get('drives/{0}/root'.format(d['id']))
        return drives

    def list_folder(self, folder):
        return self.get('drives/{0}/items/{1}/children'.format(folder['parentReference']['driveId'], folder['id']))['value']

    def expand_items(self, items):
        expanded = True
        while expanded:
            expanded = False
            for item in items:
                if 'folder' in item and 'expanded' not in item:
                    items.extend(self.list_folder(item))
                    item['expanded'] = True
                    expanded = True
                if 'fullpath' not in item:
                    if 'path' in item['parentReference']:
                        item['fullpath'] = '/'.join((
                            re.sub(
                                '/drives/[^/]+/root:',
                                '',
                                item['parentReference']['path'],
                            ),
                            item['name']
                        ))
                    else:
                        item['fullpath'] = '/'

        return items

    def download_file(self, drive_id, file_id, dest):
        url = self.get('drives/{0}/items/{1}/content'.format(drive_id, file_id))
        destdir = os.path.dirname(dest)
        if not os.path.exists(destdir):
            os.makedirs(destdir, 0755)
        with requests.get(url['location'], stream = True) as r:
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size = None):
                    f.write(chunk)
