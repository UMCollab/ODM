#!/usr/bin/env python3

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

import json
import logging

import lmdb


class Database:
    def __init__(self, path):
        self.logger = logging.getLogger(__name__)
        self.path = path
        self.db = lmdb.open(
            path,
            map_size=1048576,
            writemap=True,
            sync=False,
            subdir=False,
        )
        self.cursor = None
        self.cursor_txn = None
        self.iteration_finished = False

    def close(self):
        self.db.close()

    def read(self, key):
        key = key.encode('utf-8')
        with self.db.begin() as txn:
            val = txn.get(key)
            if val:
                return json.loads(val.decode('utf-8'))
        return {}

    def _reset_cursor(self):
        if self.cursor_txn:
            self.cursor.close()
            self.cursor_txn.abort()
            self.cursor = None
            self.cursor_txn = None

    def _write(self, key, value):
        with self.db.begin(write=True) as txn:
            txn.put(key, value)

    def write(self, key, value):
        key = key.encode('utf-8')
        value = json.dumps(value).encode('utf-8')
        tries = 0
        while True:
            try:
                self._write(key, value)
                return
            except lmdb.MapFullError:
                self._reset_cursor()
                if tries > 3:
                    raise
                new_map_size = self.db.info()['map_size'] * 2
                self.logger.info('LMDB map full, increasing to %d', new_map_size)
                self.db.set_mapsize(new_map_size)
            tries += 1

    def update(self, key, value):
        old = self.read(key)
        old.update(value)
        self.write(key, old)

    def iterate(self):
        self.iteration_finished = False
        self.cursor_txn = self.db.begin()
        self.cursor = self.cursor_txn.cursor()
        for key, value in self.cursor:
            yield (key.decode('utf-8'), json.loads(value.decode('utf-8')))
            if not self.cursor:
                return
        self._reset_cursor()
        self.iteration_finished = True
