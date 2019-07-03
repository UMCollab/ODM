#!/usr/bin/env python

# This file is part of ODM and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
import random
import time

import requests
import requests_oauthlib

from oauthlib.oauth2 import BackendApplicationClient
from statsd import StatsClient


class OneDriveSession(requests_oauthlib.OAuth2Session):
    def __init__(self, domain, ms_config, timeout, **kwargs):
        self.baseurl = 'https://graph.microsoft.com/v1.0/'
        self.logger = logging.getLogger(__name__)
        self.statsd = StatsClient(
            'localhost',
            8125,
            prefix = 'odm.onedrivesession',
        )
        self.domain = domain
        self.ms_config = ms_config
        self.timeout = timeout
        client = BackendApplicationClient(client_id = ms_config['client_id'])
        kwargs['client'] = client
        super(OneDriveSession, self).__init__(**kwargs)
        # This is just so OAuth2Session.request() will call refresh_token()
        self.auto_refresh_url = 'placeholder'
        # This is just so OAuth2Session.request() won't raise TokenUpdated
        self.token_updater = lambda x: None
        self._fresh_token()

    def _fresh_token(self):
        self.logger.debug('Fetching fresh authorization token.')
        self.fetch_token(
            token_url = 'https://login.microsoftonline.com/{}/oauth2/v2.0/token'.format(self.domain),
            client_id = self.ms_config['client_id'],
            client_secret = self.ms_config['client_secret'],
            include_client_id = True,
            scope = [
                'https://graph.microsoft.com/.default',
            ],
        )

    def refresh_token(self, token_url, **kwargs):
        self._fresh_token()

    def request(self, method, url, **kwargs):
        if not url.lower().startswith('http'):
            url = ''.join([self.baseurl, url])

        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout

        attempt = 0
        # FIXME: this should probably be configurable
        max_attempts = 30

        with self.statsd.timer(method):
            while attempt < max_attempts:
                attempt += 1
                delay = random.uniform(min(30, 2 ** attempt), min(300, 3 * 2 ** attempt))
                try:
                    result = super(OneDriveSession, self).request(method, url, **kwargs)
                except(
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.ConnectionError,
                ) as e:
                    self.logger.info(u'Retryable requests error', exc_info=e)
                    self.statsd.incr('http.error')
                else:
                    self.statsd.incr('http.{}'.format(result.status_code))
                    if result.status_code == 429:
                        self.logger.debug('throttled')
                        if 'retry-after' in result.headers:
                            delay = result.headers['retry-after']
                    elif result.status_code not in (503, 504):
                        return result

                if attempt < max_attempts:
                    self.logger.info('Sleeping for {} seconds before retrying'.format(delay))
                    self.statsd.timing('retrydelay', int(float(delay) * 1000))
                    time.sleep(float(delay))

        raise(requests.exceptions.RetryError('maximum retries exceeded'))
