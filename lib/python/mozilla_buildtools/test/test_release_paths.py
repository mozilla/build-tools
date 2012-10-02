import unittest

from release.paths import makeReleasesDir

class TestReleasesDir(unittest.TestCase):
    def testBaseReleases(self):
        got = makeReleasesDir('bbb')
        self.assertEquals('/pub/mozilla.org/bbb/releases/', got)

    def testVersioned(self):
        got = makeReleasesDir('aa', '15.1')
        self.assertEquals('/pub/mozilla.org/aa/releases/15.1/', got)

    def testRemote(self):
        got = makeReleasesDir('yy', protocol='http', server='foo.bar')
        self.assertEquals('http://foo.bar/pub/mozilla.org/yy/releases/', got)

    def testRemoteAndVersioned(self):
        got = makeReleasesDir('yx', '1.0', protocol='https', server='cee.dee')
        self.assertEquals('https://cee.dee/pub/mozilla.org/yx/releases/1.0/', got)
