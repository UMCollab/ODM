#!/usr/bin/env python

# This file is part of onedrive-magic and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import os
import re
import requests
import sys
import time

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

from util import quickxorhash

class OneDriveClient:
    def __init__(self, config, logger):
        self.baseurl = 'https://graph.microsoft.com/v1.0/'
        self.config = config
        self.logger = logger
        client = BackendApplicationClient(client_id = config['microsoft']['client_id'])
        self.msgraph = OAuth2Session(client = client)
        self._get_token()

    def _get_token(self):
        self.token = self.msgraph.fetch_token(
            token_url = 'https://login.microsoftonline.com/{}/oauth2/v2.0/token'.format(self.config.get('domain')),
            client_id = self.config['microsoft']['client_id'],
            client_secret = self.config['microsoft']['client_secret'],
            scope = [ 'https://graph.microsoft.com/.default' ],
        )

    def _get(self, path):
        if self.token['expires_at'] > time.time():
            self._get_token()

        if self.baseurl not in path:
            path = ''.join([self.baseurl, path])

        return self.msgraph.get(
            path,
            timeout = self.config.get('timeout', 60),
            allow_redirects = False,
        )

    def get(self, path):
        result = None
        page_result = None
        while not page_result:
            try:
                page_result = self._get(path)
            except requests.exceptions.ReadTimeout as e:
                self.logger.warn('Timed out...')

            if page_result.status_code == 429:
                delay = page_result.headers['retry-after']
                page_result = None
                self.logger.warn('Throttled, sleeping for {} seconds'.format(delay))
                time.sleep(delay)
            elif page_result.status_code == 302:
                return { 'location': page_result.headers['location'] }
            else:
                page_result.raise_for_status()
                decoded = json.loads(page_result.content)
                if result:
                    result['value'].extend(decoded['value'])
                else:
                    result = decoded
                if '@odata.nextLink' in decoded:
                    self.logger.debug('Getting next page...')
                    path = decoded['@odata.nextLink']
                    page_result = None

        return result

    def list_drives(self, user):
        drives = self.get('users/{}@{}/drives'.format(user, self.config['domain']))['value']
        for d in drives:
            d['root'] = self.get('drives/{}/root'.format(d['id']))
        return drives

    def list_folder(self, folder):
        return self.get('drives/{}/items/{}/children?select=file,folder,id,name,package,parentReference,remoteItem,size,fileSystemInfo'.format(folder['parentReference']['driveId'], folder['id']))['value']

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

    def download_file(self, drive_id, file_id, dest, file_hash = None):
        if file_hash and os.path.exists(dest):
            h = quickxorhash.QuickXORHash()
            if h.hash_file(dest) == file_hash:
                self.logger.debug('Existing file matched.')
                return file_hash

        url = self.get('drives/{}/items/{}/content'.format(drive_id, file_id))
        destdir = os.path.dirname(dest)
        if not os.path.exists(destdir):
            os.makedirs(destdir, 0755)

        h = quickxorhash.QuickXORHash()
        with requests.get(url['location'], stream = True) as r:
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size = 1024 * 1024):
                    f.write(chunk)
                    h.update(bytearray(chunk))
        new_hash = h.finalize()
        if file_hash and file_hash != new_hash:
            self.logger.warn('Hash mismatch: got {}, expected {}'.format(new_hash, file_hash))
            os.unlink(dest)
        return new_hash
