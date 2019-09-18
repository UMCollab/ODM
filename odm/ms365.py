#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
import os
import time
import uuid

from datetime import datetime

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

from requests.exceptions import HTTPError, RetryError

from odm import quickxorhash
from odm.util import ChunkyFile


class Container(object):
    def __init__(self, client, name):
        self.name = name
        self.client = client
        self.logger = logging.getLogger(__name__)
        self.raw = None
        self._drive = None
        self._select = None

    def show(self):
        if self._id:
            url = '{}/{}'.format(self._prefix, self._id)
            if self._select:
                url += '?$select=' + ','.join(self._select)
            result = self.client.get_list(url)
            if self.raw:
                self.raw.update(result)
            else:
                self.raw = result
            return self.raw
        else:
            return {}

    def list_drives(self):
        result = self.client.get_list('{}/{}/drives'.format(self._prefix, self._id))
        if result:
            return result['value']
        return []

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

    def _find_notebook(self, name):
        # Find the created notebook in OneDrive. I hate this.
        folder = self.drive.root.get_folder('Notebooks')
        for child in folder.children:
            if child['name'] == name:
                return Notebook(self.client, child)

    def _create_notebook(self, name):
        payload = {
            'displayName': name,
        }

        result = self.client.msgraph.post(
            '{}/{}/onenote/notebooks'.format(self._prefix, self._id),
            json = payload,
        )

        if result.status_code == 409:
            # The API might have returned a transient error, but created the
            # notebook anyway; the retry then returns a 409.
            notebook = self._find_notebook(name)
            if notebook:
                return notebook

        result.raise_for_status()

        return self._find_notebook(name)

    def create_notebook(self, name):
        notebook = None

        try:
            notebook = self._create_notebook(name)
        except HTTPError as e:
            if e.response.status_code == 409:
                # Retry with a unique name
                name += '_migrated_' + datetime.now().strftime('%Y%m%d_%H_%M')
                notebook = self._create_notebook(name)
            else:
                raise

        if notebook:
            return notebook

        raise RuntimeError('Failed to find created notebook {}'.format(name))


class Group(Container):
    def __init__(self, client, name):
        super(Group, self).__init__(client, name)
        self._prefix = 'groups'
        self._members = None
        self._owners = None
        self._site = None
        self._channels = None

        # The mail attribute probably uses the tenant name instead of the
        # friendly domain.
        search = self.client.get_list(
            "groups?$filter=startswith(mail, '{}@')".format(
                name.split('@')[0]
            )
        )['value']

        if len(search) == 0:
            self.raw = {}
            self._id = None
        else:
            if len(search) > 1:
                self.logger.warning(u'Multiple groups found for %s, using the first one', name)
            self.raw = search[0]
            self._id = self.raw['id']
            self.show()
            if 'Team' in self.raw['resourceProvisioningOptions']:
                self.raw['team'] = self.client.get_list('teams/{}'.format(self._id))

    @classmethod
    def create(cls, client, name, display_name, private = True, owners = [], members = []):
        payload = {
            'mailNickname': name.split('@')[0],
            'displayName': display_name,
            'mailEnabled': True,
            'securityEnabled': False,
            'groupTypes': [
                'Unified',
            ],
        }

        if private:
            payload['visibility'] = 'Private'

        if owners:
            payload['owners@odata.bind'] = []

            for owner in owners:
                user = User(client, client.mangle_user(owner))
                payload['owners@odata.bind'].append('https://graph.microsoft.com/v1.0/users/{}'.format(user.show()['id']))
            payload['members@odata.bind'] = list(payload['owners@odata.bind'])

        if members:
            if 'members@odata.bind' not in payload:
                payload['members@odata.bind'] = []

            for member in members:
                user = User(client, client.mangle_user(member))
                payload['members@odata.bind'].append('https://graph.microsoft.com/v1.0/users/{}'.format(user.show()['id']))

        result = client.msgraph.post('/groups', json = payload)
        result.raise_for_status()
        return cls(client, name)

    def __str__(self):
        return 'group {}'.format(self.name)

    @property
    def members(self):
        if self._members is None:
            self._members = self.client.get_list('groups/{}/members'.format(self._id))['value']
        return self._members

    @property
    def owners(self):
        if self._owners is None:
            self._owners = self.client.get_list('groups/{}/owners'.format(self._id))['value']
        return self._owners

    @property
    def site(self):
        if self._site is None:
            self._site = self.client.get_list('groups/{}/sites/root'.format(self._id))
        return self._site

    @property
    def channels(self):
        if self._channels is None:
            self._channels = self.client.get_list('teams/{}/channels'.format(self._id))['value']
        return self._channels

    def create_channel(self, name):
        payload = {
            'displayName': name,
        }
        result = self.client.msgraph.post(
            'teams/{}/channels'.format(self._id),
            json = payload,
        )
        result.raise_for_status()
        return result.json()

    def ensure_team(self):
        if 'Team' in self.raw['resourceProvisioningOptions']:
            # Already a team
            return False

        payload = {
            'guestSettings': {
                'allowCreateUpdateChannels': False,
                'allowDeleteChannels': False,
            }
        }
        result = self.client.msgraph.put(
            'groups/{}/team'.format(self._id),
            json = payload,
        )
        result.raise_for_status()
        self.raw['team'] = result.json()
        return True


class User(Container):
    def __init__(self, client, name):
        super(User, self).__init__(client, name)
        self._prefix = 'users'
        self._id = name
        self._select = [
            'accountEnabled',
            'assignedLicenses',
            'assignedPlans',
            'createdDateTime',
            'displayName',
            'givenName',
            'id',
            'jobTitle',
            'licenseAssignmentStates',
            'mail',
            'onPremisesDistinguishedName',
            'onPremisesLastSyncDateTime',
            'onPremisesProvisioningErrors',
            'onPremisesSyncEnabled',
            'surname',
            'userPrincipalName',
        ]

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


class Site(Container):
    def __init__(self, client, name):
        super(Site, self).__init__(client, name)
        self._prefix = 'sites'
        self._id = name
        self._lists = None

    @property
    def lists(self):
        if self._lists is None:
            self._lists = self.client.get_list('sites/{}/lists'.format(self._id))['value']
        return self._lists


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

    def delta(self, base, include_permissions = True):
        include_delta = False

        if not self.raw:
            return {}

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
                if include_permissions:
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

    def patch(self, payload):
        result = self.client.msgraph.patch(
            'drives/{}/items/{}'.format(
                self.raw['parentReference']['driveId'],
                self.raw['id'],
            ),
            json = payload,
        )
        result.raise_for_status()
        self.raw = result.json()

    def move(self, new_parent, new_name, force = True):
        payload = {}
        if new_parent:
            payload['parentReference'] = {
                'id': new_parent,
            }
        if new_name:
            payload['name'] = new_name

        if not payload:
            return

        if force:
            payload['@microsoft.graph.conflictBehavior'] = 'replace'

        self.patch(payload)

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
    def __init__(self, client, raw):
        super(DriveFolder, self).__init__(client, raw)
        self._children = None

    @property
    def children(self):
        if not self._children:
            self._children = self.client.get_list('drives/{}/items/{}/children'.format(self.raw['parentReference']['driveId'], self.raw['id']))['value']
        return self._children

    def get_child(self, name):
        # No leading or trailing whitespace
        name = name.strip()

        # Check to see if we already have metadata for this file
        if self._children:
            for child in self._children:
                if child['name'] == name:
                    return child

        result = self.client.msgraph.get(u'drives/{}/items/{}:/{}:/'.format(
                self.raw['parentReference']['driveId'],
                self.raw['id'],
                quote(name.encode('utf-8')),
            )
        )

        if not result.ok:
            return None

        return result.json()

    def get_folder(self, name, create = True):
        child = self.get_child(name)
        if child:
            if 'folder' not in child:
                if not create:
                    return None
                raise TypeError('{} already exists but is not a folder'.format(name))
            return DriveFolder(self.client, child)

        if not create:
            return None

        # Invalidate cache
        self._children = None

        self.logger.debug(u'Creating folder %s', name)
        payload = {
            'name': name,
            'folder': {},
            '@microsoft.graph.conflictBehavior': 'replace',
        }

        result = self.client.msgraph.post('drives/{}/items/{}/children'.format(self.raw['parentReference']['driveId'], self.raw['id']), json = payload)
        result.raise_for_status()
        return DriveFolder(self.client, result.json())

    def get_notebook(self, name, container, create = True):
        child = self.get_child(name)
        if child:
            if 'package' not in child or child['package']['type'] != 'oneNote':
                if not create:
                    return None
                raise TypeError(u'{} already exists but is not a OneNote package'.format(name))
            return Notebook(self.client, child)

        if not create:
            return None

        # Invalidate cache
        self._children = None

        self.logger.debug(u'Creating notebook %s', name)

        notebook = container.create_notebook(name)
        if notebook.raw['parentReference']['id'] != self.raw['id'] or notebook.raw['name'] != name:
            attempt = 0
            while attempt < 5:
                attempt += 1
                try:
                    notebook.move(self.raw['id'], name)
                    attempt = 5
                except HTTPError as e:
                    if e.response.status_code == 423:
                        time.sleep(5)
                    else:
                        raise

        return notebook

    def verify_file(self, src, name):
        match = self.get_child(name)

        if not match:
            return None

        try:
            stat = os.stat(src)
        except OSError:
            return None

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

    def _upload_file_simple(self, src, base_url):
        with open(src, 'rb') as f:
            result = self.client.msgraph.put(
                base_url + u'content',
                data = f,
            )
            result.raise_for_status()
            return DriveItem(self.client, result.json())

    def _upload_file_chunked(self, src, base_url, name):
        # 10 megabytes
        chunk_size = 1024 * 1024 * 10
        stat = os.stat(src)

        payload = {
            'item': {
                '@microsoft.graph.conflictBehavior': 'replace',
                'name': name,
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
                timeout = 1200,
            )
            if result.status_code == 404:
                self.logger.info('Invalid upload session')
                return None
            result.raise_for_status()
            if result.status_code == 202:
                start = int(result.json()['nextExpectedRanges'][0].split('-')[0])
                result = None

        return DriveItem(self.client, result.json())

    def upload_file(self, src, name):
        self.logger.debug(u'uploading {}'.format(src))

        # No leading or trailing whitespace
        name = name.strip()

        # Check for existing, matching file
        existing = self.verify_file(src, name)
        if existing:
            return DriveItem(self.client, existing)

        # There's not any obvious way to escape this character sequence, and
        # if we do nothing the server returns "Bad request URL"
        safe_name = name.replace('&#', '&_#')

        base_url = u'drives/{}/items/{}:/{}:/'.format(
            self.raw['parentReference']['driveId'],
            self.raw['id'],
            quote(safe_name.encode('utf-8')),
        )

        try:
            stat = os.stat(src)
        except OSError:
            return None

        item = None
        attempt = 0
        while not item and attempt < 5:
            attempt += 1
            try:
                # The documentation says 4 MB; they might actually mean MiB
                if stat.st_size < 4 * 1000 * 1000:
                    item = self._upload_file_simple(src, base_url)
                else:
                    item = self._upload_file_chunked(src, base_url, safe_name)
            except (HTTPError, RetryError):
                item = None
                if attempt < 5:
                    time.sleep(5)

        if item:
            item.patch({
                'fileSystemInfo': {
                    'lastModifiedDateTime': datetime.fromtimestamp(stat.st_mtime).isoformat() + 'Z',
                },
            })

            if name != safe_name:
                item.move(None, name)

        return item

    def _upload_file_sharepoint_simple(self, client, src, upload_url):
        with open(src, 'rb') as f:
            result = client.post(upload_url, data = f, timeout = 1200)
        result.raise_for_status()
        return result.json()

    def _upload_file_sharepoint_chunked(self, client, src, upload_url):
        # 20 MiB
        chunk_size = 1024 * 1024 * 20

        stat = os.stat(src)

        # Create temporary empty file to target with the multi-part upload
        result = client.post(upload_url)
        result.raise_for_status()
        upload_url = result.json()['d']['__metadata']['uri']

        # Argh. The returned URL isn't always valid? Escape ' -> '' (again)
        upload_url = upload_url.replace('%27', '%27%27')

        result = None
        guid = uuid.uuid4()
        start = 0

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

            if start == 0:
                url = "{}/StartUpload(uploadId=guid'{}')".format(upload_url, guid)
            elif remaining > chunk_size:
                url = "{}/ContinueUpload(uploadId=guid'{}', fileOffset={})".format(
                    upload_url, guid, start
                )
            else:
                url = "{}/FinishUpload(uploadId=guid'{}', fileOffset={})".format(
                    upload_url, guid, start
                )
            result = client.post(url, data = data, timeout = 1200)
            result.raise_for_status()

            if remaining > chunk_size:
                if start == 0:
                    start = int(result.json()['d']['StartUpload'])
                else:
                    start = int(result.json()['d']['ContinueUpload'])
                result = None

        return result.json()

    def upload_file_sharepoint(self, src, name):
        existing = self.verify_file(src, name)
        if existing:
            return DriveItem(self.client, existing)

        result = self.client.msgraph.get('drives/{}/items/{}?select=sharepointIds'.format(self.raw['parentReference']['driveId'], self.raw['id']))
        result.raise_for_status()
        result = result.json()

        site_url = result['sharepointIds']['siteUrl']
        client = self.client.sharepoint(
            site_url[0:site_url.index('/', 9) + 1],
        )

        if 'listItemId' not in result['sharepointIds']:
            # The root folder isn't actually a list item, so it doesn't have
            # a list item id.

            # fence in case I'm incorrect about why this happens
            assert self.raw['name'] == 'root'

            upload_url = "{}/_api/web/lists(guid'{}')/RootFolder".format(
                site_url,
                result['sharepointIds']['listId'],
            )
        else:
            upload_url = "{}/_api/web/lists(guid'{}')/items({})/Folder".format(
                site_url,
                result['sharepointIds']['listId'],
                result['sharepointIds']['listItemId'],
            )

        upload_url += "/Files/Add(url='{}', overwrite=true)".format(
            quote(name.replace("'", "''").encode('utf-8')),
        )

        try:
            stat = os.stat(src)
        except OSError:
            return None

        result = None
        attempt = 0
        while not result and attempt < 5:
            attempt += 1
            try:
                # In this case the limit is actually MiB, but it's on the
                # request so we want to leave a bit of breathing room.
                if stat.st_size < 250 * 1000 * 1000:
                    result = self._upload_file_sharepoint_simple(client, src, upload_url)
                else:
                    result = self._upload_file_sharepoint_chunked(client, src, upload_url)
            except (HTTPError, RetryError):
                result = None
                if attempt < 5:
                    time.sleep(5)

        return result


class Notebook(DriveFolder):
    ''' Nothing special at the moment '''
