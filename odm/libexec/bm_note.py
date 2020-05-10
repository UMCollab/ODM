#!/usr/bin/env python3

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

import os

import pypandoc

import odm.cli
from odm.boxnote import BoxNote


def main():
    cli = odm.cli.CLI(['boxnote', 'format'], client = 'box')

    note = BoxNote(cli.args.boxnote, cli.client)
    text = note.convert()

    outfile = '{}.{}'.format(cli.args.boxnote, cli.args.format)
    cssfile = os.path.join(os.path.dirname(__file__), '../boxnote.css')

    dformat = cli.args.format
    if dformat == 'pdf':
        # PDF output is special and is triggered by the .pdf file extension
        # and the use of a specific intermediate format or an explicit PDF
        # engine. wkhtmltopdf was the first one I tried that didn't choke
        # and die, so that's the one we're asking for.
        dformat = 'html'

    pypandoc.convert_text(
        text,
        dformat,
        format='json',
        outputfile=outfile,
        extra_args=[
            '-s',
            '-H', cssfile,
        ],
    )


if __name__ == '__main__':
    main()
