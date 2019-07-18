#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
import random
import time

import adal
import requests

from odm.version import VERSION


class SharepointSession(requests.Session):
    def __init__(self, site_url, ms_config, timeout, **kwargs):
        self.site_url = site_url
        super(SharepointSession, self).__init__(**kwargs)
        self.logger = logging.getLogger(__name__)
        self.ms_config = ms_config
        self.timeout = timeout
        self._fresh_token()
        self.headers.update({
            'User-Agent': 'NONISV|UniversityOfMichigan|odm/{} ({})'.format(VERSION, ms_config['client_id']),
        })

    def _fresh_token(self):
        self.logger.debug('Fetching fresh authorization token.')
        ctx = adal.AuthenticationContext('https://login.microsoftonline.com/{}.onmicrosoft.com'.format(self.ms_config['tenant']))
        self._token = ctx.acquire_token_with_client_certificate(
            self.site_url,
            self.ms_config['client_id'],
            self.ms_config['client_cert_key'],
            self.ms_config['client_cert'],
        )

    def request(self, method, url, **kwargs):
        if not url.startswith('http'):
            url = ''.join([self.site_url, url])

        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout

        headers = kwargs.get('headers', {})
        headers.update({
            'Authorization': 'Bearer ' + self._token['accessToken'],
            'Accept': 'application/json;odata=verbose'
        })
        kwargs['headers'] = headers

        attempt = 0
        # FIXME: this should probably be configurable
        max_attempts = 30
        while attempt < max_attempts:
            attempt += 1
            delay = random.uniform(min(30, 2 ** attempt), min(300, 3 * 2 ** attempt))
            try:
                result = super(SharepointSession, self).request(method, url, **kwargs)
            except(
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError,
            ) as e:
                self.logger.info(u'Retryable requests error', exc_info=e)
            else:
                if result.status_code in (400, 500):
                    self.logger.info(result.content)

                if result.status_code == 401:
                    self._fresh_token()
                elif result.status_code == 429:
                    self.logger.debug('throttled')
                    if 'retry-after' in result.headers:
                        delay = result.headers['retry-after']
                elif result.status_code not in (500, 503, 504):
                    return result

            if 'data' in kwargs and hasattr(kwargs['data'], 'read'):
                raise(requests.exceptions.RetryError('retries unavailable with file-like data'))

            if attempt < max_attempts:
                self.logger.info('Sleeping for {} seconds before retrying'.format(delay))
                time.sleep(float(delay))

        raise(requests.exceptions.RetryError('maximum retries exceeded'))
