#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import sys

import odm.cli


def main():
    odm.cli.CLI.writer_wrap(sys)
    cli = odm.cli.CLI(['action'])
    client = cli.client

    if cli.args.action == 'list-users':
        print(json.dumps(client.list_users(), indent = 2))

    elif cli.args.action == 'list-sites':
        print(json.dumps(client.list_sites(), indent = 2))

    elif cli.args.action == 'list-groups':
        print(json.dumps(client.list_groups(), indent = 2))

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
