#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
import os
import random
import string

from odm import quickxorhash
from odm.util import ChunkyFile


class Container(object):
    def __init__(self, client, name):
        self.name = name
        self.client = client
        self.logger = logging.getLogger(__name__)
        self._drive = None

    def show(self):
        return self.client.get_list('{}/{}'.format(self._prefix, self.name))

    def list_drives(self):
        return self.client.get_list('{}/{}/drives'.format(self._prefix, self._id))['value']

    def create_notebook(self, name):
        payload = {
            'displayName': name,
        }

        result = self.client.msgraph.post(
            '{}/{}/onenote/notebooks'.format(self._prefix, self._id),
            json = payload,
        )
        result.raise_for_status()

        # Find the created notebook in OneDrive. I hate this.
        folder = self.drive.root.get_folder('Notebooks')
        for child in folder.children:
            if child['name'] == name:
                return Notebook(self.client, child)

        raise RuntimeError('Failed to find created notebook {}'.format(name))


class Group(Container):
    def __init__(self, client, name):
        super(Group, self).__init__(client, name)
        self._prefix = 'groups'

        # The mail attribute probably uses the tenant name instead of the
        # friendly domain.
        self.raw = self.client.msgraph.get(
            "/groups?$filter=startswith(mail, '{}@')".format(
                name.split('@')[0]
            )
        ).json()['value'][0]

        self._id = self.raw['id']

    def __str__(self):
        return 'group {}'.format(self.name)

    @property
    def drive(self):
        if self._drive is None:
            drives = self.list_drives()

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
        self._prefix = 'users'
        self._id = name

    def __str__(self):
        return 'user {}'.format(self.name)

    @property
    def drive(self):
        if self._drive is None:
            drives = self.list_drives()

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

    def delta(self, base):
        include_delta = False

        path = 'drives/{}/root/delta?select=deleted,file,fileSystemInfo,folder,id,malware,name,package,parentReference,size'.format(self.raw['id'])

        token = base.get('token')
        if token:
            include_delta = True
            # FIXME: need to deal with expired tokens
            path += '&token={}'.format(token)

        result = self.client.get_list(path)

        base['token'] = result['@odata.deltaLink'].split('=')[-1]

        delta = {
            'deleted': [],
            'changed': [],
        }

        while len(result['value']):
            item = result['value'].pop(0)
            old = base['items'].pop(item['id'], None)
            if 'deleted' in item:
                # Save the whole old item, since we don't want to pollute
                # `items` with deleted things.
                if old:
                    delta['deleted'].append(old)

            else:
                item.update(
                    self.client.msgraph.get(
                    'drives/{}/items/{}?select=id,permissions&expand=permissions'.format(item['parentReference']['driveId'], item['id'])
                    ).json()
                )

                # Don't record inherited permissions
                perms = item.pop('permissions', None)
                if perms and 'inheritedFrom' not in perms[0]:
                    item['permissions'] = perms

                # Remove unused odata information
                for key in list(item):
                    if '@odata' in key:
                        item.pop(key, None)

                if old:
                    # Drop information about previous renames
                    old.pop('oldName', None)

                    # Save the old name if it's different
                    if old['name'] != item['name']:
                        old['oldName'] = old['name']

                    old.update(item)

                    # Only need to save the ID here, everything else should be
                    # determinable from the main entry.
                    delta['changed'].append(old['id'])

                    base['items'][item['id']] = old

                else:
                    base['items'][item['id']] = item

        if include_delta:
            base['delta'] = delta

        return base


class DriveItem(object):
    def __init__(self, client, raw):
        self.client = client
        self.raw = raw
        self.logger = logging.getLogger(__name__)

    def move(self, new_parent, new_name):
        payload = {}
        if new_parent:
            payload['parentReference'] = {
                'id': new_parent,
            }
        if new_name:
            payload['name'] = new_name

        if not payload:
            return

        result = self.client.msgraph.patch(
            'drives/{}/items/{}'.format(
                self.raw['parentReference']['driveId'],
                self.raw['id'],
            ),
            json = payload,
        )
        result.raise_for_status()
        self.raw = result.json()

    def share(self, user, roles):
        payload = {
            'sendInvitation': False,
            'requireSignIn': True,
            # FIXME: Why can't we set owner via the API?
            'roles': ['write' if x == 'owner' else x for x in roles],
            'recipients': [
                {
                    'email': user,
                },
            ],
        }

        result = self.client.msgraph.post(
            'drives/{}/items/{}/invite'.format(
                self.raw['parentReference']['driveId'],
                self.raw['id'],
            ),
            json = payload,
        )
        result.raise_for_status()

        return result.json()


class DriveFolder(DriveItem):
    @property
    def children(self):
        return self.client.get_list('drives/{}/items/{}/children'.format(self.raw['parentReference']['driveId'], self.raw['id']))['value']

    def get_folder(self, name, create = True):
        for child in self.children:
            if child['name'] == name:
                if 'folder' not in child:
                    if not create:
                        return None
                    raise TypeError('{} already exists but is not a folder'.format(name))
                return DriveFolder(self.client, child)

        if not create:
            return None

        self.logger.debug(u'Creating folder %s', name)
        payload = {
            'name': name,
            'folder': {},
            '@microsoft.graph.conflictBehavior': 'fail',
        }

        result = self.client.msgraph.post('drives/{}/items/{}/children'.format(self.raw['parentReference']['driveId'], self.raw['id']), json = payload)
        result.raise_for_status()
        return DriveFolder(self.client, result.json())

    def get_notebook(self, name, container, create = True):
        for child in self.children:
            if child['name'] == name:
                if 'package' not in child or child['package']['type'] != 'oneNote':
                    if not create:
                        return None
                    raise TypeError('{} already exists but is not a OneNote package'.format(name))
                return Notebook(self.client, child)

        if not create:
            return None

        self.logger.debug(u'Creating notebook %s', name)
        # Avoid name collisions in the fixed target folder
        tmp_name = 'odmtmp_' + ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(10))

        notebook = container.create_notebook(tmp_name)
        notebook.move(self.raw['id'], name)
        return notebook

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
            return DriveItem(self.client, existing)

        base_url = u'drives/{}/items/{}:/{}:/'.format(
            self.raw['parentReference']['driveId'],
            self.raw['id'],
            name,
        )

        # The documentation says 4 MB; they might actually mean MiB but eh.
        if stat.st_size < 4 * 1000 * 1000:
            with open(src, 'rb') as f:
                result = self.client.msgraph.put(
                    base_url + u'content',
                    data = f,
                )
                result.raise_for_status()
                return DriveItem(self.client, result.json())

        payload = {
            'item': {
                '@microsoft.graph.conflictBehavior': 'replace',
                'name': name,
                # FIXME: returns 400. Why?
#                'fileSystemInfo': {
#                    'lastModifiedDateTime': datetime.fromtimestamp(stat.st_mtime).isoformat() + 'Z',
#                },
            },
        }

        req_result = self.client.msgraph.post(
            base_url + u'createUploadSession',
            json = payload
        )
        req_result.raise_for_status()

        upload_url = req_result.json()['uploadUrl']

        start = 0
        result = None
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

        return DriveItem(self.client, result.json())


class Notebook(DriveFolder):
    ''' Nothing special at the moment '''
