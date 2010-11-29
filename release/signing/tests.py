"""
Some automated tests for signing code
"""
from unittest import TestCase

from signing import *

class TestFileParsing(TestCase):
    product = 'firefox'
    firstLocale = 'en-US'

    def testFileInfo(self):
        tests = [
                ('foo/bar/firefox-3.0.12.en-US.win32.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.0.12', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='short', leading_path='')),
                ('foo/bar/firefox-3.0.12.es.win32.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.0.12', locale='es',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='short', leading_path='')),
                ('foo/bar/firefox-3.0.12.es.win32.installer.exe',
                 'firefox',
                 dict(product='firefox', version='3.0.12', locale='es',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='short', leading_path='')),
                ('unsigned/update/win32/en-US/firefox-3.5rc3.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5rc3', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path='')),
                ('unsigned/update/win32/en-US/firefox-3.5.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path='')),
                ('unsigned/update/win32/en-US/firefox-3.5.1.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5.1', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path='')),
                ('unsigned/update/win32/en-US/firefox-3.5.12.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5.12', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path='')),
                ('unsigned/update/win32/en-US/firefox-3.6.3plugin2.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.6.3plugin2', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path='')),
                ('unsigned/update/win32/fr/firefox-3.5.1.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5.1', locale='fr',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path='')),
                ('unsigned/win32/fr/Firefox Setup 3.5.1.exe',
                 'firefox',
                 dict(product='firefox', version='3.5.1', locale='fr',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path='')),
                ('unsigned/win32/en-US/Firefox Setup 3.5.12.exe',
                 'firefox',
                 dict(product='firefox', version='3.5.12', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path='')),
                ('unsigned/win32/en-US/Firefox Setup 3.5.exe',
                 'firefox',
                 dict(product='firefox', version='3.5', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path='')),
                ('unsigned/win32/en-US/Firefox Setup 3.5 RC 3.exe',
                 'firefox',
                 dict(product='firefox', version='3.5 RC 3', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path='')),
                ('unsigned/win32/en-US/Firefox Setup 3.5 Beta 99.exe',
                 'firefox',
                 dict(product='firefox', version='3.5 Beta 99', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path='')),
                ('unsigned/win32/en-US/Firefox Setup 3.6.3plugin2.exe',
                 'firefox',
                 dict(product='firefox', version='3.6.3plugin2', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path='')),
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

    def testFiltering(self):
        """ Test that only files of the expected platform and type are passed
        through  to be signed """
        files = [
            'unsigned/linux-i686/en-US/Firefox Setup 3.6.13.exe',
            'unsigned/linux-i686/en-US/firefox-3.6.13.tar.bz2',
            'unsigned/win32/en-US/Firefox Setup 3.6.13.exe',
            'unsigned/win32/en-US/firefox-3.6.13.zip',
            'unsigned/partner-repacks/chinapack-win32/win32/en-US/Firefox Setup 3.6.13.exe',
            'unsigned/partner-repacks/google/win32/ar/Firefox Setup 3.6.13.exe',
            ]
        expected = [
            'unsigned/win32/en-US/Firefox Setup 3.6.13.exe',
            'unsigned/partner-repacks/chinapack-win32/win32/en-US/Firefox Setup 3.6.13.exe',
            'unsigned/partner-repacks/google/win32/ar/Firefox Setup 3.6.13.exe',
            ]
        self.assertEquals(filterFiles(files, self.product), expected)

    def testSorting(self):
        """ Test that the expected sort order is maintained with plain
           exes, followed by partner exes, followed by MARs"""
        files = [
            'unsigned/partner-repacks/chinapack-win32/win32/en-US/Firefox Setup 3.6.13.exe',
            'unsigned/update/win32/en-US/firefox-3.6.13.complete.mar',
            'unsigned/win32/en-US/Firefox Setup 3.6.13.exe',
            'unsigned/partner-repacks/google/win32/ar/Firefox Setup 3.6.13.exe',
            'unsigned/update/win32/ar/firefox-3.6.13.complete.mar',
            'unsigned/win32/ar/Firefox Setup 3.6.13.exe',
            ]
        sorted_files = [
            'unsigned/win32/en-US/Firefox Setup 3.6.13.exe',
            'unsigned/update/win32/en-US/firefox-3.6.13.complete.mar',
            'unsigned/win32/ar/Firefox Setup 3.6.13.exe',
            'unsigned/update/win32/ar/firefox-3.6.13.complete.mar',
            'unsigned/partner-repacks/chinapack-win32/win32/en-US/Firefox Setup 3.6.13.exe',
            'unsigned/partner-repacks/google/win32/ar/Firefox Setup 3.6.13.exe',
            ]

        results = sortFiles(files, self.product, self.firstLocale)
        self.assertEquals(results, sorted_files)

    def testChecksumVerify(self):
        """ Test that the checksum verification code is correct """
        test_invalid_checksums = [
            { 'firefox.exe' : '1', 'libnss3.dll' : '2' },
            { 'firefox.exe' : '3', 'libnss3.dll' : '2' },
            { 'firefox.exe' : '1', 'libnss3.dll' : '2' },
        ]
        test_valid_checksums = [
            { 'firefox.exe' : '1', 'libnss3.dll' : '2' },
            { 'firefox.exe' : '1', 'libnss3.dll' : '2' },
            { 'firefox.exe' : '1', 'libnss3.dll' : '2' },
        ]
        self.failUnless(not sums_are_equal(test_invalid_checksums[0], test_invalid_checksums))
        self.failUnless(sums_are_equal(test_valid_checksums[0], test_valid_checksums))


if __name__ == '__main__':
    from unittest import main
    main()
