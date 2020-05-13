#!/usr/bin/env python3

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

import json
import sys

import odm.cli


def main():
    cli = odm.cli.CLI(['action'], client='box')
    client = cli.client

    if cli.args.action == 'list-users':
        users = []
        for user in client.users():
            users.append(user.response_object)
        print(json.dumps(users, indent=2))

    else:
        print('Unsupported action {}'.format(cli.args.action), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
