#!/usr/bin/env python

# This file is part of onedrive-magic and distributed under the terms of the
# MIT license. See COPYING.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

class OneDriveClient(object):
    def __init__(self, config):
        self.baseurl = 'https://graph.microsoft.com/v1.0/'
        client = BackendApplicationClient(client_id = config['client_id'])
        self.msgraph = OAuth2Session(client = client)
        self.token = self.msgraph.fetch_token(
            token_url = 'https://login.microsoftonline.com/{0}/oauth2/v2.0/token'.format(config['domain']),
            client_id = config['client_id'],
            client_secret = config['client_secret'],
            scope = [ 'https://graph.microsoft.com/.default' ],
        )

    def get(self, path):
        result = self.msgraph.get('{0}{1}'.format(self.baseurl, path))
        return json.loads(result.content)

