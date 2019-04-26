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
    cli = odm.cli.CLI(['group', 'action'])
    client = cli.client
    groupname = client.mangle_user(cli.args.group)

    group = odm.ms365.Group(client, groupname)

    if cli.args.action == 'show':
        info = group.show()
        if info:
            info['site'] = group.site
            print(json.dumps(info, indent = 2))
        else:
            print(u'Group not found: {}'.format(groupname), file = sys.stderr)

    elif cli.args.action == 'list-members':
        print(json.dumps(group.members, indent = 2))

    elif cli.args.action == 'list-owners':
        print(json.dumps(group.owners, indent = 2))

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
