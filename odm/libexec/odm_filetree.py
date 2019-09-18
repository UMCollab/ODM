#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import datetime
import os
import sys

import odm.cli
import odm.ms365


def main():
    odm.cli.CLI.writer_wrap(sys)
    cli = odm.cli.CLI(['path', 'action', '--upload-user', '--upload-group', '--upload-path'], 'microsoft')
    client = cli.client
    dir_map = {}

    ts_start = datetime.datetime.now()
    retval = 0

    if cli.args.action in ('upload', 'verify'):
        count = 0
        size = 0

        if cli.args.upload_user:
            container = odm.ms365.User(
                client,
                client.mangle_user(cli.args.upload_user),
            )
        elif cli.args.upload_group:
            container = odm.ms365.Group(
                client,
                client.mangle_user(cli.args.upload_group),
            )
        upload_dir = container.drive.root

        if cli.args.upload_path:
            for tok in cli.args.upload_path.split('/'):
                if upload_dir:
                    upload_dir = upload_dir.get_folder(tok, cli.args.action == 'upload')

        dir_map['.'] = upload_dir

        for root, dirs, files in os.walk(unicode(cli.args.path, 'utf-8')):
            parent = os.path.relpath(root, cli.args.path)
            for dname in dirs:
                relpath = os.path.relpath('/'.join((root, dname)), cli.args.path)
                cli.logger.info(u'Working on folder %s', relpath)
                if dir_map[parent]:
                    dir_map[relpath] = dir_map[parent].get_folder(dname, cli.args.action == 'upload')
                else:
                    dir_map[relpath] = None

            for fname in files:
                count += 1
                fpath = '/'.join((root, fname))
                stat = os.stat(fpath)
                size += stat.st_size
                relpath = os.path.relpath(fpath, cli.args.path)
                cli.logger.info(u'Working on file %s', relpath)
                if cli.args.action == 'upload':
                    attempt = 0
                    result = False
                    while attempt < 3 and not result:
                        attempt += 1
                        result = dir_map[parent].upload_file(fpath, fname)
                    if not result:
                        cli.logger.warning(u'Failed to upload %s', relpath)
                        retval = 1
                elif dir_map[parent]:
                    existing = dir_map[parent].verify_file(fpath, fname)
                    if existing:
                        cli.logger.info(u'Verified %s', relpath)
                    else:
                        cli.logger.warning(u'Failed to verify %s', relpath)
                        retval = 1
                else:
                    cli.logger.warning(u'Failed to verify %s: parent folder does not exist', relpath)
                    retval = 1

        cli.logger.info(
            '%.2f MiB across %s items, elapsed time %s',
            size / (1024 ** 2),
            count,
            datetime.datetime.now() - ts_start,
        )

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        retval = 1

    sys.exit(retval)


if __name__ == '__main__':
    main()
