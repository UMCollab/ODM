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
            print(json.dumps(user, indent = 2))
        else:
            cli.logger.critical(u'User %s not found', cli.args.user)
            sys.exit(1)

    elif cli.args.action == 'list-drives':
        drives = client.list_drives(cli.args.user)
        print(json.dumps(drives, indent = 2))

    elif cli.args.action == 'list-items':
        if not client.show_user(cli.args.user):
            cli.logger.critical(u'User %s not found', cli.args.user)
            sys.exit(1)

        drives = client.list_drives(cli.args.user)

        base = {
            'items': {},
        }

        if cli.args.incremental:
            with open(cli.args.incremental, 'rb') as f:
                base = json.load(f)

        for d in drives:
            if d['name'] == 'OneDrive':
                client.delta_items(d['id'], base)

        print(json.dumps(base, indent = 2))

    elif cli.args.action == 'list-notebooks':
        # This consistently throws a 403 for some users
        try:
            notebooks = client.list_notebooks(cli.args.user)
        except HTTPError:
            notebooks = []
        print(json.dumps({ 'notebooks': notebooks }, indent = 2))

    else:
        cli.logger.critical(u'Unsupported action %s', cli.args.action)
        sys.exit(1)

if __name__ == '__main__':
    main()
