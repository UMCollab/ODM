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
    cli = odm.cli.CLI(['--dest', '--limit', '--exclude', '--start', '--diff', 'file', 'action'])
    client = cli.client

    ts_start = datetime.datetime.now()
    retval = 0

    with open(cli.args.file, 'rb') as f:
        metadata = json.load(f)

    destdir = cli.args.dest if cli.args.dest else '/var/tmp'

    if cli.args.action == 'convert-notebooks':
        for book in metadata['notebooks']:
            client.convert_notebook(book, destdir)

    elif cli.args.action in ('download', 'download-estimate', 'list-filenames', 'verify'):
        exclude = []
        if cli.args.exclude:
            with open(cli.args.exclude, 'rb') as f:
                exclude = [e.rstrip() for e in list(f)]

        size = 0
        count = 0
        started = not cli.args.start

        for item in metadata['items']:
            if not started:
                if item['fullpath'] == cli.args.start:
                    started = True
                else:
                    cli.logger.debug(u'Start point not reached, skipping item {}'.format(item['fullpath']))
                    continue

            if item['fullpath'] in exclude:
                cli.logger.debug(u'Skipping excluded item {}'.format(item['fullpath']))
                continue

            if cli.args.limit:
                if not item['fullpath'].startswith(cli.args.limit):
                    cli.logger.debug(u'Skipping non-matching item {}'.format(item['fullpath']))
                    continue

            if 'file' not in item:
                if 'folder' not in item and 'package' not in item:
                    cli.logger.debug(u'Skipping non-file {}'.format(item['fullpath']))
                continue

            if 'malware' in item:
                cli.logger.info(u'{} is tagged as malware and cannot be downloaded'.format(item['fullpath']))
                continue

            cli.logger.debug(u'Working on {}'.format(item['fullpath']))

            dest = '/'.join([destdir, item['fullpath']])
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
                    cli.logger.info(u'Downloading {} to {}'.format(item['fullpath'], dest))
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

            elif cli.args.action == 'list-filenames':
                print(item['fullpath'])

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
        fullpaths = [x['fullpath'] for x in metadata['items']]
        for root, dirs, files in os.walk(cli.args.dest):
            relpath = os.path.relpath(root, cli.args.dest)
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
