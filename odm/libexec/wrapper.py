#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import importlib
import os
import sys


def main():
    if len(sys.argv) < 2:
        print('Usage: odm <command> [<args>]', file = sys.stderr)
        sys.exit(1)

    cmd = os.path.basename(sys.argv[0])
    if cmd.startswith('odm'):
        cmd = 'odm'
    elif cmd.startswith('gdm'):
        cmd = 'gdm'
    else:
        print('Unsupported/unknown wrapper "{}"'.format(sys.argv[0]), file = sys.stderr)
        sys.exit(1)

    # Allow -c <file> to occur before the subcommand
    idx = 1
    if sys.argv[1] in ['-c', '--config']:
        idx = 3

    try:
        subcommand = importlib.import_module('odm.libexec.{}_{}'.format(cmd, sys.argv[idx]))
    except ImportError:
        print('Unsupported/unknown subcommand "{} {}"'.format(cmd, sys.argv[idx]), file = sys.stderr)
        sys.exit(1)

    sys.argv[0] += ' ' + sys.argv[idx]
    del(sys.argv[idx])
    subcommand.main()


if __name__ == '__main__':
    main()
