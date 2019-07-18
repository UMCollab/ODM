#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import sys

from requests.exceptions import HTTPError

import odm.cli
import odm.ms365


def main():
    odm.cli.CLI.writer_wrap(sys)
    cli = odm.cli.CLI(['user', 'action', '--incremental'], ['--include-permissions'])
    client = cli.client
    username = client.mangle_user(cli.args.user)

    user = odm.ms365.User(cli.client, username)

    if cli.args.action == 'show':
        print(json.dumps(user.show(), indent = 2))

    elif cli.args.action == 'list-drives':
        print(json.dumps(user.list_drives(), indent = 2))

    elif cli.args.action == 'list-items':
        if not user.show():
            cli.logger.critical(u'User %s not found', username)
            sys.exit(1)

        base = {
            'items': {},
        }

        if cli.args.incremental:
            with open(cli.args.incremental, 'rb') as f:
                base = json.load(f)

        user.drive.delta(base, include_permissions = cli.args.include_permissions)

        print(json.dumps(base, indent = 2))

    elif cli.args.action == 'list-notebooks':
        # This consistently throws a 403 for some users
        try:
            notebooks = client.list_notebooks(cli.args.user)
        except HTTPError:
            notebooks = []
        print(json.dumps({'notebooks': notebooks}, indent = 2))

    else:
        cli.logger.critical(u'Unsupported action %s', cli.args.action)
        sys.exit(1)


if __name__ == '__main__':
    main()
