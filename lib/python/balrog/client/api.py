# TODO: extend API to handle release blobs

import logging
import requests
import os

CA_BUNDLE = os.path.join(os.path.dirname(__file__),
                        '../../../../misc/mozilla-root.crt')


class API(object):

    url_template = \
        '%(api_root)s/releases/%(name)s/builds/%(build_target)s/%(locale)s'

    verify = False
    auth = None

    def __init__(self, api_root='https://balrog.build.mozilla.org',
                 auth=None, ca_certs=CA_BUNDLE, timeout=60, raise_exceptions=True):
        """ Creates an API object which wraps REST API of Balrog server.

        api_root: API root URL of balrog server
        auth    : a tuple of (username, password) or None
        ca_certs: CA bundle. It follows python-requests `verify' usage.
                  If set to False, no SSL verification is done.
                  If set to True, it tries to load a CA bundle from certifi
                  module.
                  If set to string, puthon-requests uses it as a pth to path to
                  CA bundle.
        timeout : request timeout
        raise_exceptions: Sets danger_mode parameter of python-requests config
                          which controls excpetion raising.
        """
        self.api_root = api_root.rstrip('/')
        self.verify = ca_certs
        assert isinstance(auth, tuple) or auth == None, \
               "auth should be set to tuple or None"
        self.auth = auth
        self.timeout = timeout
        self.config = dict(danger_mode=raise_exceptions)

    def request(self, url, data=None, method='GET'):
        logging.debug('Balrog request to %s' % url)
        logging.debug('Data sent: %s' % data)
        return requests.request(method=method, url=url, data=data,
                                config=self.config, timeout=self.timeout,
                                verify=self.verify, auth=self.auth)

    def update_build(self, name, product, version, build_target, locale,
                     details, copy_to=None):
        url_template_vars = dict(api_root=self.api_root, name=name,
                                 locale=locale, build_target=build_target)
        url = self.url_template % url_template_vars
        data = dict(product=product, version=version,
                    details=details)
        if copy_to:
            data['copy_to'] = copy_to

        return self.request(method='PUT', url=url, data=data)
