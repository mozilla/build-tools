"""
Some automated tests for signing code
"""
from unittest import TestCase

from signing import *

class TestFileParsing(TestCase):
    def testFileInfo(self):
        tests = [
                ('foo/bar/firefox-3.0.12.en-US.win32.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.0.12', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='short',)),
                ('foo/bar/firefox-3.0.12.es.win32.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.0.12', locale='es',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='short',)),
                ('foo/bar/firefox-3.0.12.es.win32.installer.exe',
                 'firefox',
                 dict(product='firefox', version='3.0.12', locale='es',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='short',)),
                ('unsigned/update/win32/en-US/firefox-3.5.1.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5.1', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long',)),
                ('unsigned/update/win32/fr/firefox-3.5.1.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5.1', locale='fr',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long',)),
                ('unsigned/win32/en-US/Firefox Setup 3.5.1.exe',
                 'firefox',
                 dict(product='firefox', version='3.5.1', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long',)),
                ('unsigned/win32/en-US/Firefox Setup 3.5.exe',
                 'firefox',
                 dict(product='firefox', version='3.5', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long',)),
                ('unsigned/win32/en-US/Firefox Setup 3.5 RC 3.exe',
                 'firefox',
                 dict(product='firefox', version='3.5 RC 3', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long',)),
                ('unsigned/win32/en-US/Firefox Setup 3.5 Beta 99.exe',
                 'firefox',
                 dict(product='firefox', version='3.5 Beta 99', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long',)),
                ]

        for path, product, info in tests:
            self.assertEqual(fileInfo(path, product), info)

    def testShouldSign(self):
        self.assert_(shouldSign('setup.exe'))
        self.assert_(not shouldSign('freebl3.dll'))
        self.assert_(not shouldSign('application.ini'))

    def testConvertPath(self):
        tests = [
                ('unsigned-build1/unsigned/update/win32/foo/bar', 'signed-build1/update/win32/foo/bar'),
                ('unsigned-build1/unsigned/win32/foo/bar', 'signed-build1/win32/foo/bar'),
                ('unsigned-build1/win32/foo/bar', 'signed-build1/win32/foo/bar'),
                ]
        for a, b in tests:
            self.assertEqual(convertPath(a, 'signed-build1'), b)

if __name__ == '__main__':
    from unittest import main
    main()
