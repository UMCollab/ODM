#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from odm.version import VERSION


def main():
    print('ODM version {}'.format(VERSION))


if __name__ == '__main__':
    main()
