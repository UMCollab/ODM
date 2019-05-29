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
    cli = odm.cli.CLI(['site', 'action', '--incremental'])
    client = cli.client

    site = odm.ms365.Site(client, cli.args.site)

    if cli.args.action == 'show':
        result = site.show()
        if result:
            print(json.dumps(result, indent = 2))
        else:
            print('Site {} not found'.format(cli.args.site), file = sys.stderr)
            sys.exit(1)

    elif cli.args.action == 'list-items':
        base = {
            'items': {},
        }

        if cli.args.incremental:
            with open(cli.args.incremental, 'rb') as f:
                base = json.load(f)

        site.drive.delta(base)

        print(json.dumps(base, indent = 2))

    elif cli.args.action == 'list-pages':
        print(json.dumps(client.get_list('https://graph.microsoft.com/beta/sites/{}/pages'.format(site._id)), indent = 2))

    elif cli.args.action == 'list-lists':
        print(json.dumps(site.lists, indent = 2))

        for l in site.lists:
            print(json.dumps(client.get_list('sites/{}/lists/{}/items'.format(site._id, l['id'])), indent = 2))

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
