#!/usr/bin/env python

# This file is part of onedrive-magic and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import base64
import struct

class QuickXORHash:
    def __init__(self):
        # Constants
        self.width = 160
        self.shift = 11

        # State
        self.shifted = 0
        self.length = 0
        self.data = [0] * (int((self.width - 1) / 64) + 1)

    def update(self, data):
        cur_pos = int(self.shifted / 64)
        cur_bitpos = int(self.shifted % 64)

        for i in xrange(0, min(self.width, len(data))):
            is_last = cur_pos == len(self.data) - 1
            cell_bits = 32 if is_last else 64

            new_byte = 0
            for j in xrange(i, len(data), self.width):
                new_byte ^= data[j]

            # Python doesn't have fixed-width data types, so we need to
            # explicitly throw away extra bits.
            self.data[cur_pos] ^= new_byte << cur_bitpos & 0xffffffffffffffff

            if cur_bitpos > cell_bits - 8:
                self.data[0 if is_last else cur_pos + 1] ^= new_byte >> cell_bits - cur_bitpos

            cur_bitpos += self.shift
            while cur_bitpos >= cell_bits:
                cur_pos = 0 if is_last else cur_pos + 1
                cur_bitpos -= cell_bits

        self.shifted += self.shift * (len(data) % self.width)
        self.shifted %= self.width
        self.length += len(data)

    def finalize(self):
        # Convert cells to byte array
        b_data = bytearray()
        for i in xrange(0, len(self.data)):
            chunk = struct.unpack('8B', struct.pack('Q', self.data[i]))
            if (i + 1) * 64 <= self.width:
                b_data.extend(chunk)
            else:
                b_data.extend(chunk[0:(int(self.width / 8 % 8))])

        # Convert length to byte array
        b_length = struct.unpack('8B', struct.pack('Q', self.length))

        # XOR the length with the least significant bits
        for i in xrange(0, len(b_length)):
            b_data[int(i + (self.width / 8) - len(b_length))] ^= b_length[i]

        return base64.b64encode(b_data)
