#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
import os
import random
import requests
import time

from datetime import datetime
from hashlib import md5

import google.oauth2.service_account
import google.auth.transport.requests

from odm.version import VERSION


class GoogleDriveClient:
    def __init__(self, config):
        self.baseurl = 'https://www.googleapis.com/'
        self.config = config
        self.logger = logging.getLogger(__name__)

        cred_kwargs = {
            'subject': '{}@{}'.format(config['args'].upload_user, config['domain']),
            'scopes': ['https://www.googleapis.com/auth/drive'],
        }
        self.logger.debug(cred_kwargs)
        if isinstance(config['google']['service_credentials'], dict):
            self.creds = google.oauth2.service_account.Credentials.from_service_account_info(
                config['google']['service_credentials'],
                **cred_kwargs
            )
        else:
            self.creds = google.oauth2.service_account.Credentials.from_service_account_file(
                config['google']['service_credentials'],
                **cred_kwargs
            )
        self.session = google.auth.transport.requests.AuthorizedSession(self.creds)
        self.session.headers.update({
            'User-Agent': 'odm/{}'.format(VERSION),
        })

    def _request(self, verb, path, **kwargs):
        if self.baseurl not in path:
            path = ''.join([self.baseurl, path])

        kwargs['timeout'] = self.config.get('timeout', 60)
        kwargs['allow_redirects'] = False
        return self.session.request(verb, path, **kwargs)

    def request(self, verb, path, **kwargs):
        result = None
        attempt = 0
        while not result:
            try:
                result = self._request(verb, path, **kwargs)
            except requests.exceptions.RequestException as e:
                self.logger.warning(e)
                continue

            if result.status_code == 403 and attempt > 3:
                result.raise_for_status()
            if result.status_code in [403, 429, 500, 502, 503]:
                result = None
                attempt += 1
                # Jittered backoff
                delay = random.uniform(0, min(300, 3 * 2 ** attempt))
                self.logger.info('Throttled, sleeping for {} seconds'.format(delay))
                time.sleep(delay)
            else:
                result.raise_for_status()

        return result

    def find_item(self, name, parent = None):
        query = "name = '{}' and trashed = false".format(name.replace("'", "\\'"))
        if parent:
            query = "{} and '{}' in parents".format(query, parent)

        response = self.request(
            'GET', 'drive/v3/files',
            params = {'q': query, 'fields': 'files(id,md5Checksum,size)'},
        )
        return response

    def find_file(self, name, parent = None):
        existing = self.find_item(name, parent).json()
        if len(existing['files']) > 0:
            return existing['files'][0]
        return None

    def create_file(self, name, parent = None, folder = False, mtime = None):
        existing = self.find_file(name, parent)
        if existing:
            return existing['id']

        self.logger.info('Creating {} under {}'.format(name, parent))
        payload = {
            'name': name,
        }

        if folder:
            payload['mimeType'] = 'application/vnd.google-apps.folder'
        if parent:
            payload['parents'] = [
                parent,
            ]
        if mtime:
            payload['modifiedTime'] = mtime

        return self.request(
            'POST', 'drive/v3/files',
            json = payload
        ).json()['id']

    def verify_file(self, file_name, name, parent):
        existing = self.find_item(name, parent).json()
        if len(existing['files']) == 0:
            return None

        h = md5()
        with open(file_name, 'rb') as f:
            while True:
                block = f.read(64 * 1024)
                if block:
                    h.update(block)
                else:
                    break
        ret = existing['files'][0]
        ret['verified'] = ret['md5Checksum'] == h.hexdigest()
        return ret

    def upload_file(self, file_name, name, parent):
        stat = os.stat(file_name)
        seek = 0
        attempt = 0
        path = None
        result = None
        mtime = datetime.fromtimestamp(stat.st_mtime).isoformat() + 'Z'

        if stat.st_size == 0:
            # Metadata-only creation
            self.create_file(name, parent, mtime = mtime)
            return True

        existing = self.verify_file(file_name, name, parent)
        if existing:
            if existing['verified']:
                self.logger.info('Verified {}'.format(file_name))
                return True

            upload = self.request(
                'PATCH',
                'upload/drive/v3/files/{}'.format(
                    existing['id']
                ),
                params = {
                    'uploadType': 'resumable',
                },
                headers = {'X-Upload-Content-Length': str(stat.st_size)},
                json = {
                    'modifiedTime': mtime,
                }
            )
        else:
            upload = self.request(
                'POST',
                'upload/drive/v3/files',
                params = {'uploadType': 'resumable'},
                headers = {
                    'X-Upload-Content-Length': str(stat.st_size)
                },
                json = {
                    'name': name,
                    'parents': [
                        parent,
                    ],
                    'modifiedTime': mtime,
                },
            )
        path = upload.headers['location']

        self.logger.info('Uploading {}'.format(file_name))
        while not result:
            if attempt > 0:
                # Determine the status of the upload
                try:
                    result = self.request(
                        'PUT', path,
                        headers = {'Content-Range': 'bytes */{}'.format(stat.st_size)}
                    )
                except requests.exceptions.RequestException as e:
                    self.logger.warning(e)
                    return False
                else:
                    if result.status_code in [200, 201]:
                        return True
                    elif result.status_code == 308:
                        if 'range' in result.headers:
                            seek = result.headers['range'].split('-')[1]
                        self.logger.debug('Resuming upload at byte {}'.format(seek))
                    else:
                        self.logger.warning('Upload resumption failed, HTTP {}'.format(result.status_code))
                        return False

            attempt += 1
            with open(file_name, 'rb') as f:
                f.seek(seek)
                try:
                    result = self._request(
                        'PUT', path,
                        data = f,
                        headers = {
                            'Content-Range': 'bytes {}-{}/{}'.format(
                                seek,
                                stat.st_size - 1,
                                stat.st_size,
                            )
                        },
                    )
                except requests.exceptions.RequestException as e:
                    self.logger.warning(e)

            if result is None or result.status_code == 403 or result.status_code >= 500:
                delay = random.uniform(0, min(300, 3 * 2 ** attempt))
                if result:
                    msg = 'HTTP {}'.format(result.status_code)
                else:
                    msg = 'Error'
                self.logger.info('{}, sleeping for {} seconds'.format(msg, delay))
                time.sleep(delay)
                result = None
            elif result.status_code == 308:
                # Incomplete
                result = None
            elif result.status_code == 404 or result.status_code == 410:
                # Expired upload attempt
                return False
            else:
                result.raise_for_status()
        return True
