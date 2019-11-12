#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import calendar
import dateutil
import json
import os
import sys
import time

import odm.cli


def main():
    odm.cli.CLI.writer_wrap(sys)
    cli = odm.cli.CLI(['file', 'action', '--filetree'], client = 'box')
    client = cli.client

    with open(cli.args.file, 'rb') as f:
        metadata = json.load(f)

    destdir = cli.args.filetree.rstrip('/') if cli.args.filetree else '/var/tmp'

    user_clients = {}

    if cli.args.action in ['download-items', 'list-items']:
        for item_id in metadata['items']:
            item = metadata['items'][item_id]
            if item['type'] == 'folder':
                continue

            item_path = ''
            if item['id'] != '0':
                item_path = item['name']
                parent = metadata['items'][item['parent']['id']]
                while parent['id'] != '0':
                    item_path = '/'.join([parent['name'], item_path])
                    parent = metadata['items'][parent['parent']['id']]

            if cli.args.action == 'list-items':
                print(item_path)
                continue

            cli.logger.info('Working on %s', item_path)
            item_path = '/'.join([destdir, item_path])

            if os.path.exists(item_path):
                # FIXME: verify content
                cli.logger.debug('%s already exists, skipping', item_path)
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

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
