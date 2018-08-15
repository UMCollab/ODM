#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import sys

from requests.exceptions import HTTPError

import odm.cli

def main():
    odm.cli.CLI.writer_wrap(sys)
    cli = odm.cli.CLI(['user', 'action', '--incremental'])
    client = cli.client

    if cli.args.action == 'show':
        user = client.show_user(cli.args.user)
        if user:
            print(json.dumps(client.show_user(cli.args.user), indent = 2))
        else:
            print('User {} not found'.format(cli.args.user), file = sys.stderr)
            sys.exit(1)

    elif cli.args.action == 'list-drives':
        drives = client.list_drives(cli.args.user)
        print(json.dumps(drives, indent = 2))

    elif cli.args.action == 'list-items':
        if not client.show_user(cli.args.user):
            print('User {} not found'.format(cli.args.user), file = sys.stderr)
            sys.exit(1)

        drives = client.list_drives(cli.args.user)
        items = client.expand_items([drive['root'] for drive in drives])
        if cli.args.incremental:
            with open(cli.args.incremental, 'rb') as f:
                old = json.load(f)['items']
                items = [x for x in items if x not in old]
        print(json.dumps({ 'items': items }, indent = 2))

    elif cli.args.action == 'list-notebooks':
        # This consistently throws a 403 for some users
        try:
            notebooks = client.list_notebooks(cli.args.user)
        except HTTPError:
            notebooks = []
        print(json.dumps({ 'notebooks': notebooks }, indent = 2))

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
