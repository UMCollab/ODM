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

from odm.db import Database
from odm.util import chunky_path


def _hash_file(path, h):
    with open(path, 'rb') as f:
        while True:
            block = f.read(64 * 1024)
            if block:
                h.update(block)
            else:
                break
    return h.hexdigest()


def _write_chunk(logger, path, data, size):
    logger.debug('Writing %d items to %s (%d bytes)', len(data), path, size)
    with open(path, 'wb') as f:
        f.write(json.dumps(data).encode('utf-8'))


def main():
    cli = odm.cli.CLI(['file', 'action', '--filetree', '--item-limit', '--size-limit', '--limit'], client='box')
    client = cli.client

    db = Database(cli.args.file)

    if cli.args.action == 'status':
        if db.read('_odm_meta').get('fully_expanded'):
            sys.exit(0)
        sys.exit(1)

    if cli.args.action == 'dump':
        for key, val in db.iterate():
            print(json.dumps({key: val}))
        sys.exit(0)

    if cli.args.action == 'split':
        item_limit = int(cli.args.item_limit or 1000)
        size_limit = int(cli.args.size_limit or 32)
        # gigabytes
        size_limit *= 1024 * 1024 * 1024

        fname_tmpl = cli.args.file.replace('.lmdb', '') + '.split.{:04d}.json'

        split = 0
        size = 0
        count = 0
        chunk_keys = []
        for key, item in db.iterate():
            if key.startswith('_odm_'):
                continue
            if item['type'] == 'folder':
                continue

            chunk_keys.append(key)
            size += item['size']
            if size >= size_limit or len(chunk_keys) >= item_limit:
                count += len(chunk_keys)
                split += 1
                _write_chunk(cli.logger, fname_tmpl.format(split), chunk_keys, size)
                chunk_keys = []
                size = 0
        if chunk_keys:
            _write_chunk(cli.logger, fname_tmpl.format(split), chunk_keys, size)
        cli.logger.info('Divided %d items into %d chunks', count, split)
        if db.iteration_finished:
            sys.exit(0)
        else:
            cli.logger.critical('Failed to iterate over the full database')
            sys.exit(1)

    destdir = cli.args.filetree.rstrip('/') if cli.args.filetree else '/var/tmp'

    user_clients = {}
    retval = 0

    if cli.args.action in ['download-items', 'list-items', 'verify-items']:
        limit = set()
        if cli.args.limit:
            with open(cli.args.limit, 'rb') as f:
                limit.update(json.load(f))
                print(limit)
        for key, item in db.iterate():
            if key.startswith('_odm_'):
                continue

            if item['type'] == 'folder':
                continue

            if limit and item['id'] not in limit:
                continue

            item_path = ''
            if item['id'] != '0':
                item_path_elems = [item['name']]
                parent = db.read(item['parent']['id'])
                while parent['id'] != '0':
                    item_path_elems.append(parent['name'])
                    parent = db.read(parent['parent']['id'])
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
                    digest = _hash_file(item_path, sha1())
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

            digest = _hash_file(item_path, sha1())
            if item.get('sha1', digest) != digest:
                cli.logger.warn('%s has the wrong post-download hash: expected %s, got %s', item_path, item['sha1'], digest)
                retval = 1
                continue

        sys.exit(retval)

    else:
        print('Unsupported action {}'.format(cli.args.action), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
