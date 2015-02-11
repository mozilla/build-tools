import unittest

from release.info import getBaseTag, getReleaseConfigName


class TestGetBaseTag(unittest.TestCase):
    def testRelease(self):
        self.assertEquals('FIREFOX_16_0_2', getBaseTag('firefox', '16.0.2'))

    def testBeta(self):
        self.assertEquals('FIREFOX_17_0b3', getBaseTag('firefox', '17.0b3'))

    def testEsr(self):
        self.assertEquals(
            'FIREFOX_10_0_9esr', getBaseTag('firefox', '10.0.9esr'))

    def testFennec(self):
        self.assertEquals('FENNEC_17_0', getBaseTag('fennec', '17.0'))

    def testThunderbird(self):
        self.assertEquals(
            'THUNDERBIRD_18_0b1', getBaseTag('thunderbird', '18.0b1'))


class TestGetReleaseConfigName(unittest.TestCase):
    def testFennec(self):
        got = getReleaseConfigName('fennec', 'mozilla-beta')
        self.assertEquals('release-fennec-mozilla-beta.py', got)

    def testFirefox(self):
        got = getReleaseConfigName('firefox', 'mozilla-release')
        self.assertEquals('release-firefox-mozilla-release.py', got)

    def testThunderbird(self):
        got = getReleaseConfigName('thunderbird', 'comm-esr31')
        self.assertEquals('release-thunderbird-comm-esr31.py', got)

    def testStaging(self):
        got = getReleaseConfigName('fennec', 'mozilla-release', staging=True)
        self.assertEquals('staging_release-fennec-mozilla-release.py', got)
