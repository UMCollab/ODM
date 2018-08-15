#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import datetime
import json
import os
import sys

import odm.cli

def main():
    odm.cli.CLI.writer_wrap(sys)
    cli = odm.cli.CLI(['path', 'action', 'user', '--dest'], 'google')
    client = cli.client
    dir_map = {}

    ts_start = datetime.datetime.now()
    retval = 0

    dest = cli.args.dest if cli.args.dest else 'Migrated from OneDrive'

    if cli.args.action in ('upload', 'verify'):
        count = 0
        size = 0

        parent = None
        for tok in dest.split('/'):
            if cli.args.action == 'upload':
                parent = client.create_file(tok, parent, folder = True)
            else:
                parent = client.find_file(tok, parent)
                parent = parent['id'] if parent else None
        dir_map['.'] = parent

        for root, dirs, files in os.walk(cli.args.path):
            parent = os.path.relpath(root, cli.args.path)
            for dname in dirs:
                relpath = os.path.relpath('/'.join((root, dname)), cli.args.path)
                cli.logger.info('Working on folder {}'.format(relpath))
                if cli.args.action == 'upload':
                    dir_map[relpath] = client.create_file(dname, dir_map[parent], folder = True)
                elif dir_map[parent]:
                    existing = client.find_file(dname, dir_map[parent])
                    dir_map[relpath] = existing['id'] if existing else None
                else:
                    dir_map[relpath] = None
            for fname in files:
                count += 1
                fpath = '/'.join((root, fname))
                stat = os.stat(fpath)
                size += stat.st_size
                relpath = os.path.relpath(fpath, cli.args.path)
                cli.logger.info('Working on file {}'.format(relpath))
                if cli.args.action == 'upload':
                    attempt = 0
                    result = False
                    while attempt < 3 and not result:
                        attempt += 1
                        result = client.upload_file(fpath, fname, dir_map[parent])
                    if not result:
                        cli.logger.warn('Failed to upload {}'.format(relpath))
                        retval = 1
                elif dir_map[parent]:
                    existing = client.verify_file(fpath, fname, dir_map[parent])
                    if existing:
                        if existing['verified']:
                            cli.logger.info('Verified {}'.format(relpath))
                        else:
                            cli.logger.warn('Failed to verify {}: digest mismatch'.format(relpath))
                            retval = 1
                    else:
                        cli.logger.warn('Failed to verify {}: not found'.format(relpath))
                        retval = 1
                else:
                    cli.logger.warn('Failed to verify {}: parent folder does not exist'.format(relpath))
                    retval = 1

        cli.logger.info('{:.2f} MiB across {} items, elapsed time {}'.format(
            size / (1024 ** 2),
            count,
            datetime.datetime.now() - ts_start,
        ))

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        retval = 1

    sys.exit(retval)

if __name__ == '__main__':
    main()
