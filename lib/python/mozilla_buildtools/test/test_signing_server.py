from __future__ import with_statement
# We don't support python2.5 for the server
from nose import SkipTest
import sys
if sys.version_info < (2,6,0):
    raise SkipTest


import time, shutil, tempfile
from unittest import TestCase
from StringIO import StringIO
from ConfigParser import RawConfigParser
import mock
import webob

import signing.server as ss

class TestTokens(TestCase):
    def testTokenData(self):
        now = int(time.time())
        token = ss.make_token_data("1.2.3.4", now, now+300)

        parts = token.split(":")
        self.assertEquals(parts[:-1], ["1.2.3.4", str(now), str(now+300)])

        unpacked = ss.unpack_token_data(token)
        self.assertEquals(unpacked, dict(slave_ip="1.2.3.4", valid_from=now, valid_to=now+300))

config_data = """
[server]
port = 8080
max_file_age = 600
cleanup_interval = 300

[security]
token_secret = asdfasdf
token_secret_old = 1234567890
allowed_ips = 127.0.0.0/24, 127.1.0.0/24
new_token_allowed_ips = 127.1.0.0/24
allowed_filenames = .*
min_filesize = 100
max_token_age = 600
new_token_auth = foo:bar
new_token_auth2 = fuz:baz

[paths]
signed_dir = %(tmpdir)s/signed-files
unsigned_dir = %(tmpdir)s/unsigned-files

[signing]
formats = gpg,signcode,mar,dmg
signscript = signscript.py
concurrency = 4
"""

class TestSigningServer(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_data = config_data % dict(tmpdir=self.tmpdir)

        config = RawConfigParser()
        config.readfp(StringIO(self.config_data))

        passphrases = {"gpg": "foobar"}

        self.server = ss.SigningServer(config, passphrases)

    def tearDown(self):
        self.server.stop()
        shutil.rmtree(self.tmpdir)

    def testGetToken(self):
        token = self.server.get_token("1.2.3.4", 300)
        self.assertEquals(True, self.server.verify_token(token, "1.2.3.4"))

    def testMaxTokenAge(self):
        self.assertRaises(ValueError, self.server.get_token, "1.2.3.4", 3000)

    def testExpiredToken(self):
        with mock.patch("time.time") as t:
            t.return_value = 0
            token = self.server.get_token("1.2.3.4", 300)
            t.return_value = 299
            self.assertEquals(True, self.server.verify_token(token, "1.2.3.4"))

            t.return_value = 301
            self.assertEquals(False, self.server.verify_token(token, "1.2.3.4"))

    def testBadSlaveIp(self):
        token = self.server.get_token("1.2.3.4", 300)
        self.assertEquals(False, self.server.verify_token(token, "1.2.3.5"))

    def testOldTokenSecret(self):
        self.server.token_secret = "1234567890"
        token = self.server.get_token("1.2.3.4", 300)
        self.server.token_secret = "asdfasdf"
        self.assertEquals(True, self.server.verify_token(token, "1.2.3.4"))

    def testBadOldTokenSecret(self):
        # Make sure that using a bad secret to generate the token results in
        # failure to validate
        self.server.token_secret = "bad"
        token = self.server.get_token("1.2.3.4", 300)
        self.server.token_secret = "asdfasdf"
        self.assertEquals(False, self.server.verify_token(token, "1.2.3.4"))

    def testNonce(self):
        token = self.server.get_token("1.2.3.4", 300)
        # First nonce is empty
        nonce = self.server.verify_nonce(token, "")
        self.assertTrue(nonce)

    def testNonceOldSecret(self):
        self.server.token_secret = "1234567890"
        self.server.token_secrets = ["1234567890", "asdfasdf"]
        token = self.server.get_token("1.2.3.4", 300)
        nonce = self.server.verify_nonce(token, "")
        self.assertTrue(nonce)
        self.server.token_secret = "asdfasdf"
        nonce = self.server.verify_nonce(token, nonce)
        self.assertTrue(nonce)

    def testNonceBadOldSecret(self):
        # Make sure that using a bad secret to sign the nonce results in
        # failure to validate
        self.server.token_secret = "bad"
        self.server.token_secrets = ["bad", "asdfasdf"]
        token = self.server.get_token("1.2.3.4", 300)
        nonce = self.server.verify_nonce(token, "")
        self.assertTrue(nonce)
        self.server.token_secret = "asdfasdf"
        self.server.token_secrets = ["1234567890", "asdfasdf"]
        nonce = self.server.verify_nonce(token, nonce)
        self.assertFalse(nonce)

    def testBadIp(self):
        req = webob.Request.blank("/sign/token")
        req.environ['REMOTE_ADDR'] = '128.1.0.1'
        resp = req.get_response(self.server)

        self.assertEquals(resp.status_code, 403)

    def testNewToken(self):
        req = webob.Request.blank("/token")
        req.environ['REMOTE_ADDR'] = '127.1.0.1'
        req.headers['Authorization'] = "Basic %s" % "foo:bar".encode("base64")
        req.method = 'POST'
        req.POST['slave_ip'] = "1.2.3.4"
        req.POST['duration'] = "300"
        resp = req.get_response(self.server)

        self.assertEquals(resp.status_code, 200)
        token = resp.body
        self.assertTrue(self.server.verify_token(token, "1.2.3.4"))

    def testNewTokenAuth2(self):
        req = webob.Request.blank("/token")
        req.environ['REMOTE_ADDR'] = '127.1.0.1'
        req.headers['Authorization'] = "Basic %s" % "fuz:baz".encode("base64")
        req.method = 'POST'
        req.POST['slave_ip'] = "1.2.3.4"
        req.POST['duration'] = "300"
        resp = req.get_response(self.server)

        self.assertEquals(resp.status_code, 200)
        token = resp.body
        self.assertTrue(self.server.verify_token(token, "1.2.3.4"))

    def testNewTokenBadIp(self):
        req = webob.Request.blank("/token")
        req.environ['REMOTE_ADDR'] = '127.0.0.1'
        req.headers['Authorization'] = "Basic %s" % "foo:bar".encode("base64")
        req.method = 'POST'
        req.POST['slave_ip'] = "1.2.3.4"
        req.POST['duration'] = "300"
        resp = req.get_response(self.server)

        self.assertEquals(resp.status_code, 403)

    def testNewTokenBadAuth(self):
        req = webob.Request.blank("/token")
        req.environ['REMOTE_ADDR'] = '127.1.0.1'
        req.headers['Authorization'] = "Basic %s" % "faz:faz".encode("base64")
        req.method = 'POST'
        req.POST['slave_ip'] = "1.2.3.4"
        req.POST['duration'] = "300"
        resp = req.get_response(self.server)

        self.assertEquals(resp.status_code, 401)
