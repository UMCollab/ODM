#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import calendar
import datetime
import json
import os
import sys
import time

import dateutil.parser

import odm.cli

def main():
    odm.cli.CLI.writer_wrap(sys)
    cli = odm.cli.CLI(['--filetree', '--upload-user', '--upload-path', '--limit', '--exclude', '--diff', 'file', 'action'])
    client = cli.client

    ts_start = datetime.datetime.now()
    retval = 0

    with open(cli.args.file, 'rb') as f:
        metadata = json.load(f)

    destdir = cli.args.filetree.rstrip('/') if cli.args.filetree else '/var/tmp'

    if cli.args.action == 'convert-notebooks':
        for book in metadata['notebooks']:
            client.convert_notebook(book, destdir)

    elif cli.args.action in ('download', 'download-estimate', 'list-filenames', 'verify', 'upload'):
        exclude = []
        if cli.args.exclude:
            with open(cli.args.exclude, 'rb') as f:
                exclude = [e.rstrip() for e in list(f)]

        if cli.args.action == 'upload':
            upload_user = cli.args.upload_user
            if not upload_user:
                print('No upload user specified.', file = sys.stderr)
                sys.exit(1)

            upload_path = None
            for d in client.list_drives(upload_user):
                if d['name'] == 'OneDrive':
                    upload_drive = d['id']
                    upload_path = d['root']['id']

            if not upload_path:
                print('Unable to find destination OneDrive for {}'.format(upload_dest[0]), file = sys.stderr)
                sys.exit(1)

            if cli.args.upload_path:
                for tok in cli.args.upload_path.split('/'):
                    ret = client.create_folder(upload_drive, upload_path, tok)
                    upload_path = ret['id']

        size = 0
        count = 0

        for item_id in metadata['items']:
            item = metadata['items'][item_id]
            if 'file' not in item:
                continue

            item_path = client.expand_path(item_id, metadata['items'])

            if item_path in exclude:
                cli.logger.debug(u'Skipping excluded item {}'.format(item_path))
                continue

            if cli.args.limit:
                if not item_path.startswith(cli.args.limit):
                    cli.logger.debug(u'Skipping non-matching item {}'.format(item_path))
                    continue

            cli.logger.debug(u'Working on {}'.format(item_path))

            if 'malware' in item:
                cli.logger.info(u'{} is tagged as malware and cannot be processed'.format(item_path))
                continue

            size += item['size']
            count += 1

            dest = '/'.join([destdir, client.expand_path(item_id, metadata['items'], True)])

            digest = None
            if 'hashes' in item['file']:
                digest = item['file']['hashes']['quickXorHash']

            verify_args = {
                'dest': dest,
            }
            if (not cli.args.diff) or ('size' in cli.args.diff.split(',')):
                verify_args['size'] = item['size']
            if (not cli.args.diff) or ('hash' in cli.args.diff.split(',')):
                verify_args['file_hash'] = digest

            if cli.args.action == 'download':
                verify_args['strict'] = False
                if client.verify_file(**verify_args):
                    cli.logger.info(u'Verified {}'.format(dest))
                else:
                    cli.logger.info(u'Downloading {} to {}'.format(item_path, dest))
                    attempt = 0
                    result = None
                    while attempt < 3 and result is None:
                        attempt += 1
                        result = client.download_file(
                            item['parentReference']['driveId'],
                            item['id'],
                            dest,
                        )
                        if digest and result != digest:
                            cli.logger.info(u'{} has the wrong hash, retrying'.format(dest))
                            result = None
                    if result is None:
                        cli.logger.warn(u'Failed to download {}'.format(dest))
                        retval = 1
                    else:
                        os.utime(dest, (
                            time.time(),
                            calendar.timegm(dateutil.parser.parse(
                                item['fileSystemInfo']['lastModifiedDateTime']
                            ).timetuple())
                        ))

            elif cli.args.action == 'verify' and digest:
                if client.verify_file(**verify_args):
                    cli.logger.info(u'Verified {}'.format(dest))
                else:
                    cli.logger.warn(u'Failed to verify {}'.format(dest))
                    retval = 1

            elif cli.args.action == 'upload':
                steps = []
                # Find parents by tracing up through references
                cur = item
                while 'upload_id' not in cur:
                    if 'id' not in cur['parentReference']:
                        # This is the root folder
                        cur['upload_id'] = upload_path
                    else:
                        steps.insert(0, cur)
                        cur = metadata['items'][cur['parentReference']['id']]

                for step in steps:
                    step_path = client.expand_path(step['id'], metadata['items'])
                    parent = metadata['items'][step['parentReference']['id']]
                    if parent['upload_id'] == 'skip':
                        cli.logger.debug(u'Skipping descendant {}'.format(step_path))
                        step['upload_id'] = 'skip'
                        continue

                    if 'package' in step:
                        if step['package']['type'] != 'oneNote':
                            cli.logger.info(u'Skipping unknown package {} ({})'.format(step_path, step['package']['type']))
                            step['upload_id'] = 'skip'
                            continue

                        result = client.create_notebook(
                            upload_user,
                            upload_drive,
                            parent['upload_id'],
                            step['name'],
                        )
                        if result:
                            step['upload_id'] = result['id']
                        else:
                            step['upload_id'] = 'skip'
                            cli.logger.error(u'Failed to create notebook {}'.format(step_path))
                            retval = 1

                    elif 'folder' in step:
                        result = client.create_folder(
                            upload_drive,
                            parent['upload_id'],
                            step['name'],
                        )
                        if result:
                            step['upload_id'] = result['id']
                        else:
                            step['upload_id'] = 'skip'
                            cli.logger.error(u'Failed to create folder {}'.format(step_path))
                    else:
                        result = client.upload_file(dest, upload_drive, parent['upload_id'], step['name'])
                        if result:
                            step['upload_id'] = result['id']
                        else:
                            step['upload_id'] = 'failed'
                            cli.logger.error(u'Failed to upload {}'.format(step_path))

            elif cli.args.action == 'list-filenames':
                print(item_path)

        if cli.args.action == 'download-estimate':
            delta_msg = 'wild guess time {!s}'.format(
                datetime.timedelta(seconds = int(count + (size / (24 * 1024 * 1024))))
            )
        else:
            delta_msg = 'elapsed time {!s}'.format(datetime.datetime.now() - ts_start)

        cli.logger.info('{:.2f} MiB across {} items, {}'.format(
            size / (1024 ** 2),
            count,
            delta_msg
        ))

    elif cli.args.action == 'clean-filetree':
        fullpaths = [client.expand_path(x, metadata['items'], True) for x in metadata['items'] if 'file' in metadata['items'][x]]
        for root, dirs, files in os.walk(cli.args.filetree):
            relpath = os.path.relpath(root, cli.args.filetree)
            for fname in files:
                relfpath = '/'.join([relpath, fname])
                if relfpath[:2] == './':
                    relfpath = relfpath[2:]
                if unicode(relfpath, 'utf-8') not in fullpaths:
                    cli.logger.debug('Removing {}'.format(relfpath))
                    fpath = '/'.join([root, fname])
                    os.unlink(fpath)

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        sys.exit(1)

    sys.exit(retval)

if __name__ == 'main':
    main()
