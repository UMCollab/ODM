#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import sys

import odm.cli
import odm.ms365


def main():
    odm.cli.CLI.writer_wrap(sys)
    cli = odm.cli.CLI(['group', 'action', '--display-name', '--incremental', '--owners', '--members'], ['--private'])
    client = cli.client
    groupname = client.mangle_user(cli.args.group)

    if cli.args.action == 'create':
        display_name = cli.args.display_name
        if not display_name:
            display_name = groupname.split('@')[0]

        group = odm.ms365.Group.create(
            client,
            groupname,
            display_name,
            cli.args.private,
            cli.args.owners.split(',') if cli.args.owners else [],
            cli.args.members.split(',') if cli.args.members else [],
        )

    else:
        group = odm.ms365.Group(client, groupname)

    if cli.args.action in ['show', 'create']:
        info = group.show()
        if info:
            info['site'] = group.site
            print(json.dumps(info, indent = 2))
        else:
            cli.logger.critical(u'Group %s not found', groupname)

    elif cli.args.action == 'list-members':
        print(json.dumps(group.members, indent = 2))

    elif cli.args.action == 'list-owners':
        print(json.dumps(group.owners, indent = 2))

    elif cli.args.action == 'list-items':
        if not group.show():
            cli.logger.critical(u'Group %s not found', groupname)
            sys.exit(1)

        base = {
            'items': {},
        }

        if cli.args.incremental:
            with open(cli.args.incremental, 'rb') as f:
                base = json.load(f)

        group.drive.delta(base)

        print(json.dumps(base, indent = 2))

    elif cli.args.action == 'list-channels':
        print(json.dumps(group.channels, indent = 2))

    elif cli.args.action == 'create-channel':
        if not group.show():
            cli.logger.critical(u'Group %s not found', groupname)
            sys.exit(1)

        if not cli.args.display_name:
            cli.logger.critical(u'--display-name is required for channel creation')
            sys.exit(1)

        result = group.create_channel(cli.args.display_name)
        print(json.dumps(result, indent = 2))

    elif cli.args.action == 'teamify':
        if not group.show():
            cli.logger.critical(u'Group %s not found', groupname)
            sys.exit(1)

        if not group.ensure_team():
            cli.logger.debug(u'Group %s is already a team', groupname)
        else:
            print(json.dumps(group.raw['team'], indent = 2))

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
