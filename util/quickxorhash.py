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

    def update(self, newdata):
        shifted = self.shifted

        cur_pos = int(shifted / 64)
        cur_bitpos = int(shifted % 64)

        iterations = min(self.width, len(newdata))

        for i in range(0, iterations):
            is_last = cur_pos == len(self.data) - 1
            bitsincell = 32 if is_last else 64

            if cur_bitpos <= bitsincell - 8:
                for j in range(i, len(newdata), self.width):
                    # Python doesn't have fixed-width data types, so we need to
                    # explicitly throw away bits after a left shift
                    self.data[cur_pos] ^= newdata[j] << cur_bitpos & 0xffffffffffffffff
            else:
                low = bitsincell - cur_bitpos
                newbyte = 0
                for j in range(i, len(newdata), self.width):
                    newbyte ^= newdata[j]
                self.data[cur_pos] ^= newbyte << cur_bitpos & 0xffffffffffffffff
                self.data[0 if is_last else cur_pos + 1] ^= newbyte >> low

            cur_bitpos += self.shift
            while cur_bitpos >= bitsincell:
                cur_pos = 0 if is_last else cur_pos + 1
                cur_bitpos -= bitsincell

        self.shifted += self.shift * (len(newdata) % self.width)
        self.shifted %= self.width
        self.length += len(newdata)

    def final(self):
        # Convert cells to byte array
        bytedata = bytearray()
        for i in range(0, len(self.data)):
            chunk = struct.unpack('8B', struct.pack('Q', self.data[i]))
            if (i + 1) * 64 <= self.width:
                bytedata.extend(chunk)
            else:
                bytedata.extend(chunk[0:(int(self.width / 8 % 8))])

        # Convert length to byte array
        bytelen = struct.unpack('8B', struct.pack('Q', self.length))

        # XOR the length with the least significant bits
        for i in range(0, len(bytelen)):
            bytedata[int(i + (self.width / 8) - len(bytelen))] ^= bytelen[i]

        #return ''.join('{:02x}'.format(b) for b in bytedata)
        return base64.b64encode(bytedata)
