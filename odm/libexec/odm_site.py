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
    cli = odm.cli.CLI(['site', 'action', '--incremental'])
    client = cli.client

    if cli.args.action == 'show':
        site = client.show_site(cli.args.site)
        if site:
            print(json.dumps(site, indent = 2))
        else:
            print('Site {} not found'.format(cli.args.site), file = sys.stderr)
            sys.exit(1)

    elif cli.args.action == 'list-items':
        site = client.show_site(cli.args.site)
        if not site:
            print('Site {} not found'.format(cli.args.site), file = sys.stderr)
            sys.exit(1)

        items = client.expand_items([d['root'] for d in site['drives']])
        if cli.args.incremental:
            with open(cli.args.incremental, 'rb') as f:
                old = json.load(f)['items']
                items = [x for x in items if x not in old]
        print(json.dumps({ 'items': items }, indent = 2))

    else:
        print('Unsupported action {}'.format(cli.args.action), file = sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
