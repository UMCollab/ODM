#!/usr/bin/env python3

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

import json

import odm.cli

from odm.db import Database


def main():
    cli = odm.cli.CLI(['file', 'database'], client = None)

    with open(cli.args.file, 'rb') as f:
        metadata = json.load(f)

    db = Database(cli.args.database)

    for key, item in metadata['items'].items():
        if item['type'] == 'folder':
            item['_odm_expanded'] = True
        db.write(key, item)
    db.update('_odm_meta', {'fully_expanded': True})


if __name__ == '__main__':
    main()
