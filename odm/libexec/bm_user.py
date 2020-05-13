#!/usr/bin/env python3

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

import os
import sys

import odm.cli

from odm.db import Database


def main():
    cli = odm.cli.CLI(['user', 'action', '--database'], client='box')
    client = cli.client

    if '@' not in cli.args.user:
        cli.args.user += '@' + cli.config['domain']

    user = None
    users = client.users(filter_term=cli.args.user)
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
        if not cli.args.database:
            cli.logger.critical('no database specified')
            sys.exit(1)
        db = Database(cli.args.database)

        fields = ('id', 'name', 'type', 'size', 'modified_at', 'parent', 'owned_by', 'sha1')

        folders = {
            '0': client.root_folder().get(fields=fields),
        }

        if not db.read('0'):
            db.write('0', folders['0'].response_object)
        db.update('_odm_meta', {'fully_expanded': False})

        expanded = True
        unmodified = set()
        while expanded:
            expanded = False
            for key, item in db.iterate():
                if key.startswith('_odm_'):
                    continue
                if item['type'] != 'folder':
                    continue
                if item.get('_odm_expanded') and item.get('parent') and item['parent']['id'] in unmodified:
                    # FIXME: this is better than nothing, but key order doesn't
                    # guarantee that we've already visited the parent.
                    unmodified.add(key)
                    continue
                if key not in folders:
                    folders[key] = client.folder(key).get(fields=fields)
                folder = folders[key]
                if item.get('_odm_expanded') and item['modified_at'] == folder.response_object['modified_at']:
                    unmodified.add(key)
                    continue
                item.update(folder.response_object)

                cli.logger.info('Working on %s', folder.name)
                # FIXME: how should we handle removing deleted children?
                for child in folder.get_items(fields=fields):
                    if child.owned_by != user:
                        cli.logger.info('%s has a different owner, skipping', child.name)
                        continue
                    cached = db.read(child.id)
                    cached.update(child.response_object)
                    db.write(child.id, cached)
                    if child.type == 'folder':
                        expanded = True
                        folders[child.id] = child
                item['_odm_expanded'] = True
                db.write(key, item)
                os.sync()
            if not db.iteration_finished:
                expanded = True

        db.update('_odm_meta', {'fully_expanded': True})
    else:
        print('Unsupported action {}'.format(cli.args.action), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
