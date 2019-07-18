#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import sys

import odm.cli
from odm.version import VERSION

def main():
    odm.cli.CLI.writer_wrap(sys)
    cli = odm.cli.CLI([])
    print('ODM version {}'.format(VERSION))


if __name__ == '__main__':
    main()
