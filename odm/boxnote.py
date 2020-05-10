#!/usr/bin/env python3

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

import base64
import io
import json
import logging
import os
import re
import string

from urllib.parse import unquote as url_unquote

import panflute
import puremagic

from boxsdk.exception import BoxException

from odm.util import KETSUBAN


NLIST_TYPES = [
    'LowerRoman',
    'Decimal',
    'LowerAlpha',
]

UNCHECKED = u'\u2610 '
CHECKED = u'\u2611 '


class BoxNote:
    def __init__(self, fname, client=None):
        self.logger = logging.getLogger(__name__)
        self.client = client
        with open(fname, 'rb') as f:
            self.json = json.load(f)
        self.title = os.path.basename(fname)[:-8]
        self.raw = self.json['atext']['text']
        self.attr_map = self.json['pool']['numToAttrib']

    def _process_attrs(self, raw_attrs):
        attrs = {}
        for raw in raw_attrs:
            attr = self.attr_map[raw]
            if attr[0] in ['author', 'lmkr', 'insertorder', 'start', 'align', 'bold', 'italic', 'underline', 'strikethrough']:
                attrs[attr[0]] = attr[1]
            elif attr[0] == 'list':
                attrs['list_depth'] = int(re.search(r'[0-9]+$', attr[1]).group(0))
                attrs['list_class'] = attr[1].strip(string.digits)
            elif attr[0].startswith('struct-'):
                s = attr[0].split('_')
                attrs['table_id'] = s[0].replace('struct-table', '')
                attrs['table_' + s[1][:3]] = s[1][3:]
            elif attr[0].startswith('link-'):
                # base64 encoded
                s = base64.b64decode(attr[0][5:]).decode('utf-8').split('-', 1)
                attrs['href_id'] = s[0]
                attrs['href'] = s[1]
            elif attr[0].startswith('image-'):
                s = attr[0].split('-', 2)
                # looks suspiciously like a hash
                attrs['image_id'] = s[1]
                # base64 encoded, urlencoded JSON
                attrs['image'] = json.loads(url_unquote(base64.b64decode(s[2]).decode('utf-8')))
            elif attr[0].startswith('annotation-'):
                # Some sort of opaque identifier, doesn't appear anywhere else
                # in the file and neither does my annotation text.
                attrs['annotation_id'] = attr[0].split('-', 1)[1]
            elif attr[0].startswith('font-'):
                if 'font' not in attrs:
                    attrs['font'] = {}
                s = attr[0].split('-', 2)
                attrs['font'][s[1]] = s[2]
            else:
                self.logger.debug('unhandled attribute: %s', attr)

        return attrs

    def _attr_chunks(self):
        chunks = []
        chunk_chunk = []
        text_idx = 0

        for tok in re.split(r'(\+[a-z0-9]+)', self.json['atext']['attribs']):
            if tok.startswith('*'):
                attrs = []
                newlines = 0
                for attr in re.findall(r'[*|][a-z0-9]+', tok):
                    val = int(attr[1:], 36)
                    if attr.startswith('|'):
                        newlines = val
                    else:
                        attrs.append(str(val))
            elif tok.startswith('+'):
                length = int(tok[1:], 36)
                c = {
                    'length': length,
                    'text': self.raw[text_idx:text_idx + length],
                    'attrs': self._process_attrs(attrs),
                    'newlines': newlines,
                }
                text_idx += length
                chunk_chunk.append(c)
                if newlines > 0:
                    chunks.append(chunk_chunk)
                    chunk_chunk = []
                attrs = []
            elif tok.startswith('|'):
                newlines += int(attr[1:], 36)
            elif tok:
                self.logger.error('unhandled token: %s', tok)

        if chunk_chunk:
            chunks.append(chunk_chunk)
        return chunks

    def _image(self, author, image_meta):
        ftype = 'data/png'
        b64 = KETSUBAN

        if self.client:
            try:
                f = self.client.as_user(self.client.user(author)).file(image_meta['boxFileId'])
            except BoxException as e:
                self.logger.error('Failed to download image from Box, using placeholder image', exc_info=e)
            else:
                raw = f.content()
                b64 = base64.b64encode(raw).decode('ascii')
                try:
                    ftype = puremagic.from_string(raw, mime=True, filename=image_meta.get('fileName'))
                except puremagic.PureError:
                    ftype = ''

        else:
            self.logger.debug('No Box client, using placeholder image')

        return 'data:{};base64,{}'.format(ftype, ''.join(b64.splitlines()))

    def _list(self, list_class, list_depth):
        if list_class in ['bullet', 'checklist']:
            newlist = panflute.BulletList()
        else:
            newlist = panflute.OrderedList(style=NLIST_TYPES[list_depth % 3])
        return {
            'pf': newlist,
            'class': list_class,
        }

    def convert(self):
        doc = panflute.Doc(
            api_version=(1, 17, 5),
            metadata = {
                'pagetitle': self.title,
            }
        )

        doc.content.append(panflute.Header(panflute.Str(self.title)))

        lists = {}
        tables = {}
        table_rows = {}
        table_cells = {}

        for chunk in self._attr_chunks():
            self.logger.debug(chunk)
            container = panflute.Para()
            cdiv = panflute.Div(container)

            # Handle lists
            if 'list_class' in chunk[0]['attrs']:
                lc = chunk[0]['attrs']['list_class']
                check_state = None
                if lc in ['checked', 'unchecked']:
                    check_state = lc
                    lc = 'checklist'
                ld = chunk[0]['attrs']['list_depth']

                # prune any lists that are lower than us, they're finished
                for i in list(lists.keys()):
                    if i > ld:
                        lists.pop(i)

                # non-homogenous list types can be immediately adjacent without
                # ending up merged
                if ld in lists and lists[ld]['class'] != lc:
                    lists.pop(ld)

                # checklists are a special case, they can't contain other lists
                if lc != 'checklist' and lists and lists[1]['class'] == 'checklist':
                    lists = {}

                # make sure any intermediate lists were created, including
                # the top level because boxnotes
                for i in range(1, ld + 1):
                    if i not in lists:
                        lists[i] = self._list(lc, i)
                        if i != ld:
                            lists[i]['pf'].content.append(panflute.ListItem())
                        lp = lists[i]['pf']
                        if lc == 'checklist':
                            lp = panflute.Div(lp, classes=['checklist'])
                        if i == 1:
                            doc.content.append(lp)
                        else:
                            lists[i - 1]['pf'].content[-1].content.append(lp)

                # set the container for the other subchunks
                container = panflute.Plain()
                cdiv.content = [container]
                cdiv.classes.append(lc)
                if check_state:
                    cdiv.classes.append(check_state)
                lists[ld]['pf'].content.append(panflute.ListItem(cdiv))

                if check_state == 'checked':
                    container.content.append(panflute.Str(CHECKED))
                elif check_state == 'unchecked':
                    container.content.append(panflute.Str(UNCHECKED))

            elif 'table_id' in chunk[-1]['attrs']:
                table_id = chunk[-1]['attrs']['table_id']
                row_id = chunk[-1]['attrs']['table_row']
                cell_id = row_id + chunk[-1]['attrs']['table_col']

                if table_id not in tables:
                    # There's some magic in the constructor for panflute tables
                    # that isn't exposed in any other way, so we can't create
                    # the table until we've finished populating the rows.
                    # Instead, use a placeholder div to locate it within the
                    # document.
                    tables[table_id] = {
                        'div': panflute.Div(),
                        'rows': [],
                    }
                    doc.content.append(tables[table_id]['div'])
                if row_id not in table_rows:
                    table_rows[row_id] = panflute.TableRow()
                    tables[table_id]['rows'].append(table_rows[row_id])
                if cell_id not in table_cells:
                    cdiv = panflute.Div(panflute.Plain())
                    table_cells[cell_id] = panflute.TableCell(cdiv)
                    table_rows[row_id].content.append(table_cells[cell_id])
                container = table_cells[cell_id].content[0].content[0]

            else:
                lists = {}
                doc.content.append(cdiv)

            if 'align' in chunk[0]['attrs']:
                cdiv.attributes['style'] = 'text-align: ' + chunk[0]['attrs']['align'] + ';'

            for subchunk in chunk:
                if subchunk['newlines'] > 1:
                    # we've had an extra linebreak, no more adding on to lists
                    lists = {}

                # don't do anything with markers
                if subchunk['text'] == '*' and 'lmkr' in subchunk['attrs']:
                    continue

                scont = container
                if 'href' in subchunk['attrs']:
                    scont = panflute.Link(url=subchunk['attrs']['href'])
                    container.content.append(scont)

                if 'image' in subchunk['attrs']:
                    scont.content.append(panflute.Image(url=self._image(subchunk['attrs']['author'], subchunk['attrs']['image'])))
                    continue

                span = panflute.Span()
                lines = subchunk['text'].splitlines()
                while lines:
                    subtext = lines.pop(0)
                    span.content.append(panflute.Str(subtext))
                    if lines:
                        span.content.append(panflute.LineBreak())

                if 'font' in subchunk['attrs']:
                    color = subchunk['attrs']['font'].get('color', '000000')
                    size = subchunk['attrs']['font'].get('size', 'medium')
                    span.classes.append('font-size-' + size)
                    span.classes.append('font-color-' + color)

                    # I don't actually know what the possible colors are and I
                    # don't feel like finding out, so just inject it as an
                    # inline style.
                    if color != '000000':
                        span.attributes['style'] = 'color: #' + color + ';'

                if subchunk['attrs'].get('underline'):
                    span.classes.append('underline')
                if subchunk['attrs'].get('bold'):
                    span = panflute.Strong(span)
                if subchunk['attrs'].get('italic'):
                    span = panflute.Emph(span)
                if subchunk['attrs'].get('strikethrough'):
                    span = panflute.Strikeout(span)
                scont.content.append(span)

        # Actually create the tables
        for x in tables:
            tables[x]['div'].content.append(panflute.Table(*tables[x]['rows']))

        with io.StringIO() as f:
            panflute.dump(doc, f)
            return f.getvalue()
