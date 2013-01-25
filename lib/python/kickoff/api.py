import os
import requests
try:
    import simplejson as json
except ImportError:
    import json

CA_BUNDLE = os.path.join(os.path.dirname(__file__),
                         '../../../../misc/certs/ca-bundle.crt')

import logging
log = logging.getLogger(__name__)


def is_csrf_token_expired(token):
    from datetime import datetime
    expiry = token.split('##')[0]
    if expiry <= datetime.now().strftime('%Y%m%d%H%M%S'):
        return True
    return False


class API(object):
    auth = None
    url_template = None

    def __init__(self, auth, api_root, ca_certs=CA_BUNDLE, timeout=60,
                 raise_exceptions=True):
        self.api_root = api_root.rstrip('/')
        self.auth = auth
        self.verify = ca_certs
        self.timeout = timeout
        self.config = dict(danger_mode=raise_exceptions)
        self.session = requests.session()
        self.csrf_token = None

    def request(self, params=None, data=None, method='GET', url_template_vars={}):
        url = self.api_root + self.url_template % url_template_vars
        if method != 'GET' and method != 'HEAD':
            if not self.csrf_token or is_csrf_token_expired(self.csrf_token):
                res = self.session.request(method='HEAD', url=self.api_root + '/csrf_token',
                                           config=self.config, timeout=self.timeout,
                                           auth=self.auth)
                self.csrf_token = res.headers['X-CSRF-Token']
            data['csrf_token'] = self.csrf_token
        log.debug('Request to %s' % url)
        log.debug('Data sent: %s' % data)
        try:
            return self.session.request(method=method, url=url, data=data,
                                        config=self.config, timeout=self.timeout,
                                        auth=self.auth, params=params)
        except requests.HTTPError, e:
            log.error('Caught HTTPError: %s' % e.response.content)
            raise


class Releases(API):
    url_template = '/releases'

    def getReleases(self, ready=1, complete=0):
        return json.loads(self.request(params={'ready': ready, 'complete': complete}).content)


class Release(API):
    url_template = '/releases/%(name)s'

    def getRelease(self, name):
        return json.loads(self.request(url_template_vars={'name': name}).content)

    def update(self, name, **data):
        url_template_vars = {'name': name}
        return self.request(method='POST', data=data, url_template_vars=url_template_vars).content


class ReleaseL10n(API):
    url_template = '/releases/%(name)s/l10n'

    def getL10n(self, name):
        return self.request(url_template_vars={'name': name}).content
