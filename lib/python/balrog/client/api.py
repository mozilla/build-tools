# TODO: extend API to handle release blobs
import logging
import requests
import os

CA_BUNDLE = os.path.join(os.path.dirname(__file__),
                        '../../../../misc/certs/ca-bundle.crt')

def is_csrf_token_expired(token):
    from datetime import datetime
    expiry = token.split('##')[0]
    if expiry <= datetime.now().strftime('%Y%m%d%H%M%S'):
        return True
    return False

class API(object):
    """A class that knows how to make requests to a Balrog server, including
       pre-retrieving CSRF tokens and data versions.

       url_template: The URL to submit to when request() is called. Standard
                     Python string interpolation can be used here in
                     combination with the url_template_vars argument to
                     request().
       prerequest_url_template: Before submitting the real request, a HEAD
                                operation will be done on this URL. If the
                                HEAD request succeeds, it is expected that
                                there will be X-CSRF-Token and X-Data-Version
                                headers in the response. If the HEAD request
                                results in a 404, another HEAD request to
                                /csrf_token will be made in attempt to get a
                                CSRF Token. This URL can use string
                                interpolation the same way url_template can.
                                In some cases this may be the same as the
                                url_template.
    """
    verify = False
    auth = None
    url_template = None
    prerequest_url_template = None

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
        self.session = requests.session()
        self.csrf_token = None

    def request(self, data=None, method='GET', url_template_vars={}):
        url = self.api_root + self.url_template % url_template_vars
        prerequest_url = self.api_root + self.prerequest_url_template % url_template_vars
        # If we'll be modifying things, do a GET first to get a CSRF token
        # and possibly a data_version.
        if method != 'GET' and method != 'HEAD':
            # Use the URL of the resource we're going to modify first,
            # because we'll need its data_version if it exists.
            try:
                res = self.do_request(prerequest_url, None, 'HEAD', {})
                data['data_version'] = res.headers['X-Data-Version']
                # We may already have a non-expired CSRF token, but it's
                # faster/easier just to set it again even if we do, since
                # we've already made the request.
                data['csrf_token'] = self.csrf_token = res.headers['X-CSRF-Token']
            except requests.HTTPError, e:
                # However, if the resource doesn't exist yet we may as well
                # not bother doing another request solely for a token unless
                # we don't have a valid one already.
                if e.response.status_code != 404:
                    raise
                if not self.csrf_token or is_csrf_token_expired(self.csrf_token):
                    res = self.do_request(self.api_root + '/csrf_token', None, 'HEAD', {})
                    data['csrf_token'] = self.csrf_token = res.headers['X-CSRF-Token']

            logging.debug('Got CSRF Token: %s' % self.csrf_token)
        return self.do_request(url, data, method, url_template_vars)

    def do_request(self, url, data, method, url_template_vars):
        logging.debug('Balrog request to %s' % url)
        logging.debug('Data sent: %s' % data)
        try:
            return self.session.request(method=method, url=url, data=data,
                                        config=self.config, timeout=self.timeout,
                                        verify=self.verify, auth=self.auth)
        except requests.HTTPError, e:
            logging.error('Caught HTTPError: %s' % e.response.content)
            raise


class SingleLocale(API):
    url_template = '/releases/%(name)s/builds/%(build_target)s/%(locale)s'
    prerequest_url_template = '/releases/%(name)s'

    def update_build(self, name, product, version, build_target, locale,
                     buildData, copyTo=None):
        url_template_vars = dict(api_root=self.api_root, name=name,
                                 locale=locale, build_target=build_target)
        data = dict(product=product, version=version,
                    data=buildData)
        if copyTo:
            data['copyTo'] = copyTo

        return self.request(method='PUT', data=data,
                            url_template_vars=url_template_vars)
