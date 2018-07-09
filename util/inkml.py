#!/usr/bin/env python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import svgwrite

from bs4 import BeautifulSoup

class InkML:
    def __init__(self, src):
        with open(src, 'r') as f:
            ink = BeautifulSoup(f, 'xml')

        self.ink = ink

        self.traces = []

        self.brushes = {}
        for brush in ink.find_all('inkml:brush'):
            brush_dict = {}
            for prop in brush.find_all('inkml:brushProperty'):
                brush_dict[prop['name']] = prop['value']
            self.brushes[brush['xml:id']] = brush_dict

        self.contexts = {}
        for ctx in ink.find_all('inkml:context'):
            for fmt in ctx.find_all('inkml:traceFormat'):
                if ctx['xml:id'] in self.contexts:
                    raise ValueError("unsupported inkML (multiple trace formats?)")
                self.contexts[ctx['xml:id']] = [x['name'] for x in fmt.find_all('inkml:channel')]

    def _parse_channels(self, context, point):
        retval = {}
        for chan, value in zip(self.contexts[context], point.split(' ')):
            retval[chan] = value
        return retval

    def save(self, dest, split = False):
        real_dest = dest
        canvas = None

        iteration = 0
        for trace in self.ink.find_all('inkml:trace'):
            if canvas is None:
                if '{}' in dest:
                    real_dest = dest.format(iteration)
                    print(real_dest)
                    self.traces.append(real_dest)
                canvas = svgwrite.Drawing(real_dest, (32767, 32767), profile='tiny')
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
                coords = self._parse_channels(trace['contextRef'][1:], point)
                if path is None:
                    path = canvas.path('M{},{}'.format(coords['X'], coords['Y']), **extra)
                path.push('L{},{}'.format(coords['X'], coords['Y']))
            if path:
                canvas.add(path)
                if split:
                    canvas.save()
                    canvas = None
            iteration += 1

        if canvas:
            canvas.save()
