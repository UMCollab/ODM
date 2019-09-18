#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import base64
import logging
import os

import requests
import requests_toolbelt

from bs4 import BeautifulSoup

from odm import inkml, onedrivesession, quickxorhash, sharepointsession


KETSUBAN = '''
iVBORw0KGgoAAAANSUhEUgAAAMkAAADhCAYAAABiOZFeAAAFVElEQVR42u3dvW1bMRSAUffuvGNG
SJsRPIen8wpKKzzAFHl1L3+s8wGqZMUIxFPQ5CPf3iRpZh/v77f7V29//3z++Gr97DP/TuRzvmFB
AokggUSLuwVrDdLoYK8A5BsWJJAIEkgECSR6DSQZg7sCrG9YkEAiSCDRoUgq5g9Z8xVIBAkkggQS
QQKJzkUysv6RMSHPQNLKNyxIIBEkkGhx31//bvev6vnJyPpKxrqMb1iQQCJIIBEkkGjvro/v3oOp
eC/rEV2P7woSSAQJJDqk6wC7zlGyX9G5BSSCBBJBAokggUS/s4p1korHfqP7xnzDggQSQQKJFtda
07i+Wj/X+14UVPT3+YYFCSSCBBJBAon2bvZpixV/AHBgtiCBRJBAooPmJNVPEc44nM46iSCBRJBA
Ikgg0bkT9+oB3VrTiL6skwgSSAQJJNq4rG3tFVveo/Mj6ySCBBJBAokggUTnIsmYVLe2249AyPj9
vmFBAokggUSLm3E4Xe+aRnSLjK3yggQSQQKJIIFE59aaWK9eJ4msmTjBUZBAIkgg0eZIIvOMR2sj
vXOQ6M9aJxEkkAgSSAQJJDq36wDLuIxn5NFe97gLEkgECSR6MSTRE1Gigzvjc9ZJBAkkggQSQQKJ
zi1rW3vv2kjVffBOSxEkkAgSSLRpFdvTK+5h9GSiIIFEkEAiSCDRa0zcKw63zj6VceQPCr5hQQKJ
IIFEG89Jsu4uqb6G2pxEkEAiSCARJJAor+gjqzPuKawY7Bn/pq3ykEACiSCBRBPmCFnbRKJb5Xtf
WddQu6IaEkggESSQCBJIVFP0RMUokqw9Ur0HWGed/Nj7nhEFCSSQQAIJJFowJ/lpDlIB5vqzkAgS
SAQJJIIEEkHS+4eBilNPZqyT2LsFCSSQQAIJJGoUPb1k9Tb66kPmzEkECSSCBBJBAonmVLF3a2SA
RddNetdQsu5M9PguJJBAIkggUdI6ScbTgFl3GFafbFJxcJ0RBQkkkEACCSSCBBKtmbhHB2YGyqzT
UqITd5f4QAIJJJBAAokGkPSeQhJ9qrA1+FpbZLK2ntiWIkggESSQCBJItPc6yewTHKOnpfTu65q9
/d6IggQSSCCBBBI9mJNUX++8+qnFiu0skEACCSSQQAKJIIFE8Xa6qz3rEdrq39f6Y4QRBQkkkEAC
CSS6NONwuvtaaxoVSCrWflprNkYUJJBAAgkkkAgSSDTWdTBkbJUfeS96AkvGvq7oq/WIsBEFCSSQ
QAIJJHowJ8m4NzC6LSX6ZGJr/tAa4NH3rJNAAgkkggQSQQKJzkUyAqF38hx9fDf6nnUSSCCBRJBA
oifWSSruBMnY4h79XPWayRW6EQUJJJBAAgkkggQSPYekupFLgzLWSWa8TNwhgQQSSCCBRBshmXEo
d/UdJO4ngQQSSAQJJIIEEr0GkurTJB2YLUggESSQaEKz1xSyBnQ1tOgjBEYUJJBAAgkkkAgSSLT3
xL3iXsToAd0jJ0haJ4EEEkgECST6hUgq5ha9B9BFt/QbUZBAAgkkkEAiSCDRHCSz719fuf9r5P9k
REECCSSQQAKJLu20Bb3i9824T9H9JJBAAgkkkEAiSCDRfCQVdyZmbZXPgB59GVGQQAIJJJBAoqR1
kpFBGh2IGZ/LWkPxZCIkkEAiSCARJJBo74l79YQ4Wtbju63PucQHEkgggQQSSFSAZMY29+g8Z+X2
eyMKEkgggQQSSAQJJFozce8dVLNPXanYfm+dBBJIIBEkkGigUw6Zq/j9FWCNKEgggQQSSCCRJEmS
JEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSjuo/MassmDD1NGYAAAAASUVORK5CYII=
'''


class OneDriveClient:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.msgraph = onedrivesession.OneDriveSession(self.config.get('domain'), self.config['microsoft'], self.config.get('timeout', 60))
        self._sharepoint = {}

    def sharepoint(self, site_url):
        if site_url not in self._sharepoint:
            self._sharepoint[site_url] = sharepointsession.SharepointSession(
                site_url,
                self.config['microsoft'],
                self.config.get('timeout', 60),
            )
        return self._sharepoint[site_url]

    def mangle_user(self, username):
        if not username:
            return None
        if '@' in username:
            return username
        return '@'.join((username, self.config['domain']))

    def get_list(self, path):
        result = None
        page_result = None

        while not page_result:
            page_result = self.msgraph.get(path, allow_redirects = False)

            if page_result.status_code == 302:
                return {
                    'location': page_result.headers['location']
                }
            elif page_result.status_code == 404:
                return None
            else:
                page_result.raise_for_status()
                decoded = page_result.json()

                if result:
                    result['value'].extend(decoded['value'])
                else:
                    result = decoded

                for key in decoded:
                    if key not in ['value', '@odata.nextLink']:
                        result[key] = decoded[key]

                if '@odata.nextLink' in decoded:
                    self.logger.debug('Getting next page...')
                    path = decoded['@odata.nextLink']
                    page_result = None

        return result

    def list_users(self):
        users = self.get_list(
            'users?$select=id,displayName,givenName,jobTitle,mail,userPrincipalName,accountEnabled,onPremisesImmutableId,onPremisesSyncEnabled'
        )
        if users:
            return users['value']
        return []

    def list_sites(self):
        return self.get_list('sites?search=')['value']

    def list_groups(self):
        return self.get_list('groups')['value']

    def expand_path(self, item_id, items, fs_safe = False):
        path = []

        while 'id' in items[item_id]['parentReference']:
            name = items[item_id]['name']

            i = 0
            while fs_safe and len(name.encode('utf-8')) > 255:
                # Many Unix filesystems only allow filenames <= 255 bytes. Find
                # the longest string that will fit in 255 bytes once encoded.
                for j in range(0, len(name)):
                    if len(name[:j].encode('utf-8')) > 255:
                        j -= 1
                        break
                # Add it as a separate dir and remove it from the name
                path.insert(i, name[:j])
                i += 1
                name = name[j:]

            path.insert(i, name)
            item_id = items[item_id]['parentReference']['id']

        if path:
            return '/'.join(path)
        return '/'

    def verify_file(self, dest, size = None, file_hash = None, strict = True):
        if not os.path.exists(dest):
            self.logger.info(u'{} does not exist'.format(dest))
            return False

        if strict and size is None and file_hash is None:
            self.logger.debug(u'No size or hash provided for {}'.format(dest))
            return False

        if size is not None:
            stat = os.stat(dest)
            if stat.st_size != size:
                self.logger.info(u'{} is the wrong size: expected {}, got {}'.format(dest, size, stat.st_size))
                return False

        if file_hash:
            h = quickxorhash.QuickXORHash()
            real_hash = h.hash_file(dest)
            if real_hash != file_hash:
                self.logger.info(u'{} has the wrong hash: expected {}, got {}'.format(dest, file_hash, real_hash))
                return False

        return True

    def _download(self, url, dest, calculate_hash = False):
        destdir = os.path.dirname(dest)
        if not os.path.exists(destdir):
            os.makedirs(destdir, 0o0755)

        h = None
        if calculate_hash:
            h = quickxorhash.QuickXORHash()

        try:
            with self.msgraph.get(url, stream = True, timeout = self.config.get('timeout', 60) * 20) as r:
                r.raise_for_status()
                if r.headers['content-type'].startswith('multipart/'):
                    decoder = requests_toolbelt.MultipartDecoder.from_response(r)
                    for part in decoder.parts:
                        with open('{}.{}'.format(dest, part.headers['content-type'].split(';')[0].replace('/', '_')), 'wb') as f:
                            f.write(part.content)
                else:
                    with open(dest, 'wb') as f:
                        for chunk in r.iter_content(chunk_size = 1024 * 1024):
                            f.write(chunk)
                            if h is not None:
                                h.update(bytearray(chunk))
        except requests.exceptions.RequestException as e:
            self.logger.warning(e)
            return None
        if calculate_hash:
            return h.finalize()
        return True

    def download_file(self, drive_id, file_id, dest):
        url = self.get_list('drives/{}/items/{}/content'.format(drive_id, file_id))

        if url:
            return self._download(url['location'], dest, True)
        else:
            self.logger.error('Failed to fetch download link from API')
            return None

    def list_notebooks(self, user):
        notebooks = self.get_list('users/{}@{}/onenote/notebooks?expand=sections'.format(user, self.config['domain']))
        if notebooks:
            for n in notebooks['value']:
                for s in n['sections']:
                    s['pages'] = self.get_list(s['pagesUrl'])['value']
            return notebooks['value']
        return []

    def _convert_page(self, page_url, page_name, dest, quirky):
        if not os.path.exists(dest + '/data'):
            os.makedirs(dest + '/data', 0o0755)
        raw_path = '/'.join([dest, 'raw', page_name, 'api_response'])
        result = self._download(page_url, raw_path)
        ink_file = '.'.join([raw_path, 'application_inkml+xml'])
        converter = inkml.InkML(ink_file)
        svg_file = '{}/data/{}.ink.{}'.format(dest, page_name, '{}.svg')
        converter.save(svg_file, quirky)
        raw_file = '.'.join([raw_path, 'text_html'])
        with open(raw_file, 'rb') as f:
            html = BeautifulSoup(f, 'lxml')

        # Download images and update references
        for img in html.find_all('img'):
            img_id = img['data-fullres-src'].split('/')[7].split('!')[0]
            img_file = '{}/data/{}.{}'.format(dest, img_id, img['data-fullres-src-type'].split('/')[1])
            img['src'] = 'data/' + os.path.basename(img_file)
            self._download(img['data-fullres-src'], img_file)
            for cruft in ('data-fullres-src', 'data-fullres-src-type', 'data-src-type'):
                if img.get(cruft):
                    del img[cruft]

        # Download objects and turn them into links
        for obj in html.find_all('object'):
            obj_id = obj['data'].split('/')[7]
            obj_file = '{}/data/{}.{}'.format(dest, obj_id, obj['data-attachment'])
            link = html.new_tag(
                'a',
                href = 'data/' + os.path.basename(obj_file),
                download = obj['data-attachment']
            )
            link.append(obj['data-attachment'])
            self._download(obj['data'], obj_file)
            obj.replace_with(link)

        # Check for failed export. Notably, mathematical expressions don't work.
        unexported = False
        for div in html.find_all('div'):
            if ' Processing ParagraphNode failed ' in div.contents:
                unexported = True
                if quirky:
                    # Add a visual indicator of missing data
                    img = html.new_tag('img', src = 'data/ketsuban.png')
                    div.append(img)

        if unexported:
            self.logger.warning(u'{} contained unexportable data'.format(dest))
            with open(dest + '/data/ketsuban.png', 'wb') as f:
                f.write(base64.b64decode(KETSUBAN))

        # Add InkML SVG, if it was generated
        for ink in converter.traces:
            div = html.new_tag('div', style = "position:absolute;left:0px;top:0px;pointer-events:none")
            replaced = False
            if quirky:
                # OneNote Online renders ink on top of other contents, not at
                # its normal Z location. I like this code so I'm leaving it in,
                # but disabling it by default.
                for child in html.body.children:
                    if child == ' InkNode is not supported ' and not replaced:
                        child.replace_with(div)
                        replaced = True
            if not replaced:
                html.body.append(div)
            img = html.new_tag(
                'img',
                src = 'data/' + os.path.basename(ink),
                height = '{}px'.format(converter.pixel_dimensions['Y'])
            )
            div.append(img)

        with open('{}/{}.html'.format(dest, page_name), 'wb') as f:
            f.write(html.prettify(formatter = 'html').encode('utf-8'))
        return result

    def convert_notebook(self, metadata, destdir, quirky = False):
        # quirk mode is less faithful to the official rendering, but more
        # amusing to me
        html = BeautifulSoup('<html><head></head><body></body></html>', 'lxml')
        title = html.new_tag('title')
        title.string = metadata['displayName']
        html.head.append(title)

        basedir = '/'.join([destdir, metadata['displayName']])
        if not os.path.exists(basedir):
            os.makedirs(basedir, 0o0755)

        for section in metadata['sections']:
            div = html.new_tag('div')
            html.body.append(div)
            heading = html.new_tag('h2')
            heading.string = section['displayName']
            div.append(heading)
            page_list = html.new_tag('ul')
            div.append(page_list)

            for page in section['pages']:
                self._convert_page(
                    page['contentUrl'] + '?includeInkML=true',
                    page['id'],
                    basedir,
                    quirky,
                )

                link = html.new_tag('a', href = page['id'] + '.html')
                link.string = page['title'] if page['title'] else 'Untitled Page'
                li = html.new_tag('li')
                li.append(link)
                page_list.append(li)

        with open('/'.join([destdir, metadata['displayName'], 'index.html']), 'wb') as f:
            f.write(html.prettify(formatter = 'html').encode('utf-8'))
