#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import os
import random
import re
import requests
import sys
import time

import requests
import requests_oauthlib
import requests_toolbelt

from bs4 import BeautifulSoup
from oauthlib.oauth2 import BackendApplicationClient

from util import inkml, quickxorhash

class OneDriveClient:
    def __init__(self, config, logger):
        self.baseurl = 'https://graph.microsoft.com/v1.0/'
        self.config = config
        self.logger = logger
        client = BackendApplicationClient(client_id = config['microsoft']['client_id'])
        self.msgraph = requests_oauthlib.OAuth2Session(client = client)
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
        attempt = 0

        while not page_result:
            attempt += 1
            error = None
            delay = random.uniform(0, min(300, 3 * 2 ** attempt))
            try:
                page_result = self._get(path)
            except (
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError,
            ) as e:
                self.logger.warn(e)
                error = 'requests error'

            if page_result.status_code == 429:
                delay = page_result.headers['retry-after']
                error = 'Throttled'
            elif page_result.status_code == 504:
                error = 'Gateway timeout'

            if error:
                self.logger.warn('{}, sleeping for {} seconds'.format(error, delay))
                time.sleep(delay)
                page_result = None
                continue

            if page_result.status_code == 302:
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
                    attempt = 0

        return result

    def list_users(self):
        users = self.get('users')
        return users['value']

    def show_user(self, user):
        return self.get('/users/{}@{}'.format(user, self.config['domain']))

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

    def verify_file(self, dest, size, file_hash = None):
        if size is None and file_hash is None:
            self.logger.debug(u'No size or hash provided for {}'.format(dest))
            return False

        if not os.path.exists(dest):
           self.logger.debug(u'{} does not exist'.format(dest))
           return False

        if size is not None:
            stat = os.stat(dest)
            if stat.st_size != size:
                self.logger.debug(u'{} is the wrong size: expected {}, got {}'.format(dest, size, stat.st_size))
                return False

        if file_hash:
            h = quickxorhash.QuickXORHash()
            real_hash = h.hash_file(dest)
            if real_hash != file_hash:
                self.logger.debug(u'{} has the wrong hash: expected {}, got {}'.format(dest, file_hash, real_hash))
                return False

        return True

    def _download(self, url, dest, calculate_hash = False):
        destdir = os.path.dirname(dest)
        if not os.path.exists(destdir):
            os.makedirs(destdir, 0755)

        h = None
        if calculate_hash:
            h = quickxorhash.QuickXORHash()

        try:
            with self.msgraph.get(url, stream = True) as r:
                r.raise_for_status()
                if r.headers['content-type'].startswith('multipart/'):
                    decoder = requests_toolbelt.MultipartDecoder.from_response(r)
                    for part in decoder.parts:
                        with open('{}.{}'.format(dest, part.headers['content-type'].split(';')[0].replace('/', '_')), 'wb') as f:
                            f.write(part.content)
                else:
                    with open(dest, 'wb') as f:
                        for chunk in r.iter_content(chunk_size = 1024 * 1024):
                            f.write(chunk)
                            if h is not None:
                                h.update(bytearray(chunk))
        except (
            requests.exceptions.HTTPError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError
        ) as e:
            self.logger.warn(e)
            return None
        if calculate_hash:
            return h.finalize()
        return True

    def download_file(self, drive_id, file_id, dest):
        url = self.get('drives/{}/items/{}/content'.format(drive_id, file_id))

        return self._download(url['location'], dest, True)

    def list_notebooks(self, user):
        notebooks = self.get('users/{}@{}/onenote/notebooks?expand=sections'.format(user, self.config['domain']))['value']
        for n in notebooks:
            for s in n['sections']:
                s['pages'] = self.get(s['pagesUrl'])['value']
        return notebooks

    def download_page(self, page_url, dest):
        result = self._download(page_url + '?includeInkML=true', dest)
        ink_file = '{}.{}'.format(dest, 'application_inkml+xml')
        converter = inkml.InkML(ink_file)
        svg_file = '{}.{}'.format(dest, 'svg')
        converter.save(svg_file)
        raw_file = '{}.{}'.format(dest, 'text_html')
        with open(raw_file, 'rb') as f:
            html = BeautifulSoup(f, 'lxml')
        for img in html.find_all('img'):
            img_id = img['data-fullres-src'].split('/')[7].split('!')[0]
            img_file = '{}/{}.{}'.format(os.path.dirname(dest), img_id, img['data-fullres-src-type'].split('/')[1])
            img['src'] = os.path.basename(img_file)
            self._download(img['data-fullres-src'], img_file)
        if not converter.empty:
            div = html.new_tag('div', style = "position:absolute;left:0px;top:0px")
            # Technically this should be several different SVGs in divs at
            # multiple positions in the body, but rendering the full InkML
            # beneath everything is the best we can do with what the API
            # actually gives us.
            html.body.insert(0, div)
            img = html.new_tag('img', src = os.path.basename(svg_file), height = '1238px')
            div.append(img)
        html_file = '{}.{}'.format(dest, 'html')
        with open(html_file, 'wb') as f:
            f.write(html.prettify(formatter = 'html').encode('utf-8'))
        return result
