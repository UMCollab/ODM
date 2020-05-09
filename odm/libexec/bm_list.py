#!/usr/bin/env python3

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

import calendar
import dateutil
import json
import os
import sys
import time

from hashlib import sha1

import odm.cli

from odm.util import chunky_path


def _hash_file(path):
    h = sha1()
    with open(path, 'rb') as f:
        while True:
            block = f.read(64 * 1024)
            if block:
                h.update(block)
            else:
                break
    return h.hexdigest()


def main():
    cli = odm.cli.CLI(['file', 'action', '--filetree'], client = 'box')
    client = cli.client

    with open(cli.args.file, 'rb') as f:
        metadata = json.load(f)

    destdir = cli.args.filetree.rstrip('/') if cli.args.filetree else '/var/tmp'

    user_clients = {}
    retval = 0

    if cli.args.action in ['download-items', 'list-items', 'verify-items']:
        for item_id in metadata['items']:
            item = metadata['items'][item_id]
            if item['type'] == 'folder':
                continue

            item_path = ''
            if item['id'] != '0':
                item_path_elems = [item['name']]
                parent = metadata['items'][item['parent']['id']]
                while parent['id'] != '0':
                    item_path_elems.append(parent['name'])
                    parent = metadata['items'][parent['parent']['id']]
                item_path_elems.reverse()
                item_path = '/'.join([x for y in item_path_elems for x in chunky_path(y)])
            if cli.args.action == 'list-items':
                print(item_path)
                continue

            cli.logger.info('Working on %s', item_path)
            item_path = '/'.join([destdir, item_path])

            if os.path.exists(item_path):
                digest = None
                if 'sha1' in item:
                    digest = _hash_file(item_path)
                if item.get('sha1') == digest:
                    cli.logger.debug('%s successfully verified', item_path)
                    continue
                elif digest:
                    cli.logger.info('%s has the wrong hash: expected %s, got %s', item_path, item['sha1'], digest)
                    if cli.args.action == 'verify-items':
                        retval = 1
                        continue
            elif cli.args.action == 'verify-items':
                cli.logger.info('%s does not exist', item_path)
                retval = 1
                continue

            filedir = os.path.dirname(item_path)
            if not os.path.exists(filedir):
                os.makedirs(filedir, 0o0755)

            if item['owned_by']['id'] not in user_clients:
                user_clients[item['owned_by']['id']] = client.as_user(client.user(item['owned_by']['id']))

            with open(item_path, 'wb') as f:
                user_clients[item['owned_by']['id']].file(item['id']).download_to(f)

            os.utime(
                item_path,
                (
                    time.time(),
                    calendar.timegm(
                        dateutil.parser.parse(item['modified_at']).timetuple()
                    )
                )
            )

            if 'sha1' in item:
                digest = _hash_file(item_path)
                if digest != item['sha1']:
                    cli.logger.warn('%s has the wrong post-download hash: expected %s, got %s', item_path, item['sha1'], digest)
                    retval = 1

        sys.exit(retval)

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
