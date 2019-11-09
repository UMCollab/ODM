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
    cli = odm.cli.CLI(['user', 'action'], client = 'box')
    client = cli.client

    if '@' not in cli.args.user:
        cli.args.user += '@' + cli.config['domain']

    user = None
    users = cli.client.users(filter_term=cli.args.user)
    for u in users:
        if user:
            cli.logger.critical('"%s" matched more than one user.', cli.args.user)
            sys.exit(1)
        user = u

    if not user:
        cli.logger.critical('No user matching "%s" found.', cli.args.user)
        sys.exit(1)

    client = cli.client.as_user(user)

    if cli.args.action == 'list-items':
        items = {}
        items['0'] = client.root_folder().get()
        expanded = set()
        seen = set(['0'])
        while expanded != seen:
            for key in items.keys():
                item = items[key]
                if item.type == 'folder' and item.id not in expanded:
                    for child in item.get_items(fields = ['id', 'name', 'type', 'size', 'modified_at', 'parent', 'owned_by', 'sha1']):
                        if child.owned_by != user:
                            cli.logger.info('%s has a different owner, skipping', child.name)
                            continue
                        items[child.id] = child
                        if child.type == 'folder':
                            seen.add(child.id)
                    expanded.add(item.id)

        json_items = {}
        for key in items.keys():
            json_items[key] = items[key].response_object

        print(json.dumps({'items': json_items}, indent = 2))

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
