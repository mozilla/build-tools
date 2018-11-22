import unittest

from release.paths import makeReleasesDir, makeCandidatesDir


class TestReleasesDir(unittest.TestCase):

    def testBaseReleases(self):
        got = makeReleasesDir('bbb')
        self.assertEquals('/pub/bbb/releases/', got)

    def testVersioned(self):
        got = makeReleasesDir('aa', '15.1')
        self.assertEquals('/pub/aa/releases/15.1/', got)

    def testRemote(self):
        got = makeReleasesDir('yy', protocol='http', server='foo.bar')
        self.assertEquals('http://foo.bar/pub/yy/releases/', got)

    def testRemoteAndVersioned(self):
        got = makeReleasesDir('yx', '1.0', protocol='https', server='cee.dee')
        self.assertEquals(
            'https://cee.dee/pub/yx/releases/1.0/', got)
