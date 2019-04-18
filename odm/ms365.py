#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
import os

from odm import quickxorhash
from odm.util import ChunkyFile


class Container(object):
    def __init__(self, client, name):
        self.name = name
        self.client = client
        self.logger = logging.getLogger(__name__)
        self._drive = None



class Group(Container):
    def __init__(self, client, name):
        super(Group, self).__init__(client, name)

    def __str__(self):
        return 'group {}'.format(self.name)

    @property
    def drive(self):
        if self._drive is None:
            drives = self.client.list_drives(self.name, 'groups')

            obj = {}
            if drives:
                obj = drives[0]

                if len(drives) > 1:
                    self.logger.warning(u'Multiple drives found for %s, using the first one', self.name)

            self._drive = Drive(self.client, obj)

        return self._drive


class User(Container):
    def __init__(self, client, name):
        super(User, self).__init__(client, name)

    def __str__(self):
        return 'user {}'.format(self.name)

    @property
    def drive(self):
        if self._drive is None:
            drives = self.client.list_drives(self.name, 'users')

            obj = {}
            for d in drives:
                if d['name'] == 'OneDrive':
                    obj = d

            self._drive = Drive(self.client, obj)

        return self._drive


class Drive(object):
    def __init__(self, client, raw):
        self.client = client
        self.raw = raw

        if raw:
            self.root = DriveFolder(client, client.get_list('drives/{}/root'.format(raw['id'])))

    def __bool__(self):
        return bool(self.raw)

    def __str__(self):
        return self.raw.get('id', 'None')


class DriveFolder(object):
    def __init__(self, client, raw):
        self.client = client
        self.raw = raw
        self.logger = logging.getLogger(__name__)

    @property
    def children(self):
        return self.client.get_list('drives/{}/items/{}/children'.format(self.raw['parentReference']['driveId'], self.raw['id']))['value']

    def create_folder(self, name):
        for child in self.children:
            print(child)
            if child['name'] == name:
                if 'folder' not in child:
                    raise TypeError('{} already exists but is not a folder'.format(name))
                return DriveFolder(self.client, child)

        self.logger.debug(u'Creating folder %s', name)
        payload = {
            'name': name,
            'folder': {},
            '@microsoft.graph.conflictBehavior': 'fail',
        }

        result = self.client.msgraph.post('drives/{}/items/{}/children'.format(self.raw['parentReference']['driveId'], self.raw['id']))
        result.raise_for_status()
        return DriveFolder(self.client, result.json())

    def verify_file(self, src, name):
        match = None
        for child in self.children:
            if child['name'] == name:
                match = child
                break

        if not match:
            return None

        stat = os.stat(src)
        if stat.st_size != match['size']:
            return None

        self.logger.info(u'Verified size of uploaded {}'.format(src))

        if 'hashes' not in match['file']:
            # Probably a OneNote file.
            return match

        h = quickxorhash.QuickXORHash()
        fhash = h.hash_file(src)
        if fhash == match['file']['hashes']['quickXorHash']:
            self.logger.info(u'Verified uploaded {}'.format(src))
            return match

        return None

    def upload_file(self, src, name):
	# 10 megabytes
        chunk_size = 1024 * 1024 * 10

        self.logger.debug(u'uploading {}'.format(src))
        stat = os.stat(src)

        #Check for existing, matching file
        existing = self.verify_file(src, name)
        if existing:
            return existing

        # The documentation says 4 MB; they might actually mean MiB but eh.
        if stat.st_size < 4 * 1000 * 1000:
            with open(src, 'rb') as f:
                result = self.msgraph.put(u'drives/{}/items/{}:/{}:/content'.format(drive_id, parent, fname), data=f)
            result.raise_for_status()
            return result.json()

        payload = {
            'item': {
                '@microsoft.graph.conflictBehavior': 'replace',
                'name': fname,
                # FIXME: returns 400. Why?
#                'fileSystemInfo': {
#                    'lastModifiedDateTime': datetime.fromtimestamp(stat.st_mtime).isoformat() + 'Z',
#                },
            },
        }

        upload_req = self.msgraph.post(u'drives/{}/items/{}:/{}:/createUploadSession'.format(drive_id, parent, fname), json=payload)
        upload_req.raise_for_status()

        upload = upload_req.json()
        upload_url = upload['uploadUrl']

        while not result:
            remaining = stat.st_size - start
            if remaining > chunk_size:
                end = start + chunk_size - 1
                size = chunk_size
            else:
                end = stat.st_size - 1
                size = stat.st_size - start

            self.logger.debug('uploading bytes {}-{}/{}'.format(start, end, stat.st_size))

            data = ChunkyFile(src, start, size)
            result = self.client.msgraph.put(
                upload_url,
                data = data,
                headers = {
                    'Content-Length': str(size),
                    'Content-Range': 'bytes {}-{}/{}'.format(start, end, stat.st_size),
                },
                timeout = 1200, # FIXME: what should this actually be?
            )
            if result.status_code == 404:
                self.logger.info('Invalid upload session')
                # FIXME: retry
                return None
            result.raise_for_status()
            if result.status_code == 202:
                start = int(result.json()['nextExpectedRanges'][0].split('-')[0])
                result = None

        return result.json()

