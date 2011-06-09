import unittest

from release.versions import getL10nDashboardVersion

class TestBuildVersions(unittest.TestCase):
    def _doTest(self, expected, version):
        self.assertEquals(expected,
                          getL10nDashboardVersion(version, "firefox"))

    def testPointRelease(self):
        self._doTest("fx4.0.1", "4.0.1")

    def testBeta(self):
        self._doTest("fx5_beta_b3", "5.0b3")
