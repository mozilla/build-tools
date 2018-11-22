import re
import unittest

from build.versions import ANY_VERSION_REGEX


class TestAnyVersionRegex(unittest.TestCase):
    avr = '^%s$' % ANY_VERSION_REGEX

    def testAlpha(self):
        self.assertTrue(re.match(self.avr, '3.0a1'))

    def testBeta(self):
        self.assertTrue(re.match(self.avr, '3.0b12'))

    def testEsr(self):
        self.assertTrue(re.match(self.avr, '10.0.4esr'))

    def testEsrPre(self):
        self.assertTrue(re.match(self.avr, '10.0.5esrpre'))

    def testBad(self):
        self.assertFalse(re.match(self.avr, '3.0c'))
