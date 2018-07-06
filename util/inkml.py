#!/usr/bin/env python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import svgwrite

from bs4 import BeautifulSoup

class InkML:
    def __init__(self, src):
        self.empty = True

        with open(src, 'r') as f:
            ink = BeautifulSoup(f, 'xml')

        self.ink = ink

        for d in ink.find_all('inkml:trace'):
            self.empty = False

        if self.empty:
            return

        self.brushes = {}
        for brush in ink.find_all('inkml:brush'):
            brush_dict = {}
            for prop in brush.find_all('inkml:brushProperty'):
                brush_dict[prop['name']] = prop['value']
            self.brushes[brush['xml:id']] = brush_dict

    def save(self, dest):
        if self.empty:
            return

        canvas = svgwrite.Drawing(dest, (32767, 32767), profile='tiny')
        for trace in self.ink.find_all('inkml:trace'):
            brush = self.brushes[trace['brushRef'][1:]]
            extra = {
                'stroke': brush['color'],
                'stroke_width': max(int(brush['width']), int(brush['height'])),
                'opacity': 1.0 - float(brush['transparency']),
                'fill': 'none',
            }

            if brush['tip'] == 'ellipse':
                extra['stroke_linecap'] = 'round'
                extra['stroke_linejoin'] = 'round'
            path = None
            for point in trace.text.split(', '):
                x, y = point.split(' ')
                if path is None:
                    path = canvas.path('M{},{}'.format(x,y), **extra)
                path.push('L{},{}'.format(x,y))
            if path:
                canvas.add(path)

        canvas.save()
