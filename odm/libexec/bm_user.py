#!/usr/bin/env python3

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

import os
import sys
import uuid

from boxsdk.exception import BoxAPIException

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

        meta = db.read('_odm_meta')
        cli.logger.debug('Meta %s', meta)
        if meta.get('fully_expanded') or 'color' not in meta:
            meta['color'] = str(uuid.uuid4())
            cli.logger.debug('Reset color to %s', meta['color'])
        meta['fully_expanded'] = False
        db.write('_odm_meta', meta)

        root = db.read('0')
        if '_odm_color' not in root:
            root['_odm_color'] = meta['color']
        root.update(folders['0'].response_object)
        db.write('0', root)

        expanded = True
        unmodified = {}
        deleted = set()
        while expanded:
            expanded = False
            for key, item in db.iterate():
                if key.startswith('_odm_'):
                    continue

                cli.logger.debug('Working on %s', item['name'])
                parents = []
                if item['type'] == 'folder':
                    parents.append(item)
                parent = item.get('parent')
                while parent:
                    parents.append(db.read(parent['id']))
                    parent = parents[-1].get('parent')

                while parents:
                    pobj = parents.pop()
                    pid = pobj['id']
                    if pid == '0':
                        continue
                    if pid in unmodified or pid in deleted:
                        continue
                    ocolor = pobj.get('_odm_color')
                    if pobj['parent'] and ocolor and ocolor != meta['color'] and ocolor == unmodified.get(pobj['parent']['id'], 'mu'):
                        expanded = True
                        unmodified[pid] = ocolor
                    else:
                        if pid not in folders:
                            try:
                                folders[pid] = client.folder(pid).get(fields=fields)
                            except BoxAPIException as e:
                                if e.status == 404:
                                    deleted.add(pid)
                                    continue
                                raise
                        if ocolor and ocolor != meta['color'] and pobj['modified_at'] == folders[pid].response_object['modified_at']:
                            expanded = True
                            unmodified[pid] = ocolor

                if item['type'] != 'folder' or key in deleted:
                    continue

                if key in unmodified:
                    if item['_odm_color'] != meta['color']:
                        db.update(key, {'_odm_color': meta['color']})
                    continue

                if item.get('_odm_expanded') and item['_odm_color'] == meta['color']:
                    continue

                folder = folders[key]

                item.update(folder.response_object)
                item['_odm_color'] = meta['color']
                item['_odm_child_color'] = meta['color']

                cli.logger.info('Working on %s', folder.name)
                for child in folder.get_items(fields=fields):
                    if child.owned_by != user:
                        cli.logger.info('%s has a different owner, skipping', child.name)
                        continue
                    cobj = db.read(child.id)
                    if cobj.get('_odm_color') != meta['color']:
                        if cobj.get('modified_at') == child.response_object['modified_at']:
                            if child.response_object['type'] == 'folder':
                                if cobj.get('_odm_expanded'):
                                    unmodified[child.id] = cobj['_odm_color']
                            else:
                                cobj['_odm_modified'] = False
                        else:
                            if child.response_object['type'] == 'folder':
                                cobj['_odm_expanded'] = False
                            else:
                                cobj['_odm_modified'] = True
                    cobj.update(child.response_object)
                    cobj['_odm_color'] = meta['color']
                    if child.type == 'folder':
                        expanded = True
                        folders[child.id] = child
                    db.write(child.id, cobj)
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
