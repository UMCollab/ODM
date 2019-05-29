#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import base64
import logging
import struct

from ctypes import cdll, c_char_p, c_void_p, c_ulonglong


class QuickXORHash:
    def __init__(self):
        logger = logging.getLogger(__name__)
        try:
            self.libqxh = cdll.LoadLibrary('libqxh.so.0')
        except OSError:
            self.HAS_LIBQXH = False
            logger.debug('Using pure Python for hash calculation')
        else:
            self.HAS_LIBQXH = True
            logger.debug('Using libqxh for hash calculation')
            self.libqxh.qxh_new.restype = c_void_p
            self.libqxh.qxh_update.argtypes = [c_void_p, c_char_p, c_ulonglong]
            self.libqxh.qxh_finalize.argtypes = [c_void_p]
            self.libqxh.qxh_finalize.restype = c_char_p
            self.libqxh.qxh_free.argtypes = [c_void_p]
            self.qxh = self.libqxh.qxh_new()
            return

        # Constants
        self.width = 160
        self.shift = 11

        # State
        self.shifted = 0
        self.length = 0
        self.cell = [0] * (int((self.width - 1) / 64) + 1)

    def update(self, data):
        if self.HAS_LIBQXH:
            self.libqxh.qxh_update(self.qxh, str(data), len(data))
            return

        cell_index = int(self.shifted / 64)
        cell_bitpos = int(self.shifted % 64)

        for i in range(0, min(self.width, len(data))):
            next_cell = cell_index + 1
            cell_bits = 64
            # Last cell needs to wrap around
            if next_cell == len(self.cell):
                next_cell = 0
                # Last cell usually isn't a full 64 bits
                if self.width % 64 > 0:
                    cell_bits = self.width % 64

            new_byte = 0
            for j in range(i, len(data), self.width):
                new_byte ^= data[j]

            # Python doesn't have fixed-width data types, so we need to
            # explicitly throw away extra bits.
            self.cell[cell_index] ^= new_byte << cell_bitpos & 0xffffffffffffffff

            if cell_bitpos > cell_bits - 8:
                self.cell[next_cell] ^= new_byte >> (cell_bits - cell_bitpos)

            cell_bitpos += self.shift
            if cell_bitpos >= cell_bits:
                cell_index = next_cell
                cell_bitpos -= cell_bits

        self.shifted += self.shift * (len(data) % self.width)
        self.shifted %= self.width
        self.length += len(data)

    def finalize(self):
        if self.HAS_LIBQXH:
            digest = self.libqxh.qxh_finalize(self.qxh)
            self.libqxh.qxh_free(self.qxh)
            return digest

        # Convert cells to byte array
        b_data = bytearray()
        for i in range(0, len(self.cell)):
            chunk = struct.unpack('8B', struct.pack('Q', self.cell[i]))
            if (i + 1) * 64 <= self.width:
                b_data.extend(chunk)
            else:
                b_data.extend(chunk[0:int(self.width / 8 % 8)])

        # Convert length to byte array
        b_length = struct.unpack('8B', struct.pack('Q', self.length))

        # XOR the length with the least significant bits
        offset = int((self.width / 8) - len(b_length))
        for i in range(0, len(b_length)):
            b_data[i + offset] ^= b_length[i]

        return base64.b64encode(b_data)

    def hash_file(self, path):
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(512 * 1024)
                if chunk:
                    self.update(bytearray(chunk))
                else:
                    break
        return self.finalize()
