"""
Some automated tests for signing code
"""
import subprocess
from unittest import TestCase

from signing import *

class TestFileParsing(TestCase):
    product = 'firefox'
    firstLocale = 'en-US'

    def _doFileInfoTest(self, path, product, info):
        self.assertEqual(fileInfo(path, product), info)

    def testShortPathenUSMar(self):
        self._doFileInfoTest(
                'foo/bar/firefox-3.0.12.en-US.win32.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.0.12', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='short', leading_path=''))

    def testShortPathLocaleMar(self):
        self._doFileInfoTest(
                'foo/bar/firefox-3.0.12.es.win32.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.0.12', locale='es',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='short', leading_path=''))

    def testShortPathLocaleExe(self):
        self._doFileInfoTest(
                'foo/bar/firefox-3.0.12.es.win32.installer.exe',
                 'firefox',
                 dict(product='firefox', version='3.0.12', locale='es',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='short', leading_path=''))

    def testLongPathenUSMarRC(self):
        self._doFileInfoTest(
                'unsigned/update/win32/en-US/firefox-3.5rc3.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5rc3', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path=''))

    def testLongPathenUSMarFinal(self):
        self._doFileInfoTest(
                'unsigned/update/win32/en-US/firefox-3.5.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path=''))

    def testLongPathenUSMarPointRelease(self):
        self._doFileInfoTest(
                'unsigned/update/win32/en-US/firefox-3.5.1.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5.1', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path=''))

    def testLongPathenUSMarPointRelease2(self):
        self._doFileInfoTest(
                'unsigned/update/win32/en-US/firefox-3.5.12.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5.12', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path=''))

    def testLongPathenUSMarProjectBranch(self):
        self._doFileInfoTest(
                'unsigned/update/win32/en-US/firefox-3.6.3plugin2.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.6.3plugin2', locale='en-US',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path=''))

    def testLongPathLocaleMarPointRelease(self):
        self._doFileInfoTest(
                'unsigned/update/win32/fr/firefox-3.5.1.complete.mar',
                 'firefox',
                 dict(product='firefox', version='3.5.1', locale='fr',
                     platform='win32', contents='complete', format='mar',
                     pathstyle='long', leading_path=''))

    def testLongPathLocaleExePointRelease(self):
        self._doFileInfoTest(
                'unsigned/win32/fr/Firefox Setup 3.5.1.exe',
                 'firefox',
                 dict(product='firefox', version='3.5.1', locale='fr',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path=''))

    def testLongPathenUSExePointRelease(self):
        self._doFileInfoTest(
                'unsigned/win32/en-US/Firefox Setup 3.5.12.exe',
                 'firefox',
                 dict(product='firefox', version='3.5.12', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path=''))

    def testLongPathenUSExeFinal(self):
        self._doFileInfoTest(
                'unsigned/win32/en-US/Firefox Setup 3.5.exe',
                 'firefox',
                 dict(product='firefox', version='3.5', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path=''))

    def testLongPathenUSExeRC(self):
        self._doFileInfoTest(
                'unsigned/win32/en-US/Firefox Setup 3.5 RC 3.exe',
                 'firefox',
                 dict(product='firefox', version='3.5 RC 3', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path=''))

    def testLongPathenUSExeBeta(self):
        self._doFileInfoTest(
                'unsigned/win32/en-US/Firefox Setup 3.5 Beta 99.exe',
                 'firefox',
                 dict(product='firefox', version='3.5 Beta 99', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path=''))

    def testLongPathenUSExeProjectBranch(self):
        self._doFileInfoTest(
                'unsigned/win32/en-US/Firefox Setup 3.6.3plugin2.exe',
                 'firefox',
                 dict(product='firefox', version='3.6.3plugin2', locale='en-US',
                     platform='win32', contents='installer', format='exe',
                     pathstyle='long', leading_path=''))

    def testLongPathEUBallotBuild(self):
        self._doFileInfoTest(
                'unsigned/win32-EUballot/de/Firefox Setup 3.6.14.exe',
                 'firefox',
                 dict(product='firefox', version='3.6.14', locale='de',
                      platform='win32', contents='installer', format='exe',
                      pathstyle='long', leading_path='win32-EUballot/'))

    def testLongPathPartnerRepack(self):
        self._doFileInfoTest(
                'unsigned/partner-repacks/chinapack-win32/win32/zh-CN/Firefox Setup 3.6.14.exe',
                 'firefox',
                 dict(product='firefox', version='3.6.14', locale='zh-CN',
                      platform='win32', contents='installer', format='exe',
                      pathstyle='long', leading_path='partner-repacks/chinapack-win32/'))

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

    def testWin32DownloadRules(self):
        """ Test that the rsync logic works as expected:
              - No hidden files/dirs
              - No previously signed binaries
              - No partial mars
              - No checksums
              - No detached sigs
        """
        try:
            os.makedirs("./test-download/update/win32")
            os.makedirs("./test-download/win32")
            os.makedirs("./test-download/unsigned/win32/.foo")
            os.makedirs("./test-download/unsigned/win32/foo")
            open("./test-download/unsigned/win32/.foo/hello.complete.mar", "w").write("Hello\n")
            open("./test-download/unsigned/win32/foo/hello.complete.mar", "w").write("Hello\n")
            open("./test-download/win32/hello.complete.mar", "w").write("Hello\n")
            open("./test-download/unsigned/win32/hello.partial.mar", "w").write("Hello\n")
            open("./test-download/unsigned/win32/hello.checksums", "w").write("Hello\n")
            open("./test-download/unsigned/win32/hello.asc", "w").write("Hello\n")
            subprocess.check_call([
                'rsync',
                '-av',
                '--exclude-from',
                'download-exclude.list',
                './test-download/',
                './test-dest/' ])
            self.failUnless(not os.path.isdir("./test-dest/win32"))
            self.failUnless(not os.path.isdir("./test-dest/update/win32"))
            self.failUnless(not os.path.isdir("./test-dest/unsigned/win32/.foo/"))
            self.failUnless(not os.path.exists("./test-dest/unsigned/win32/.foo/hello.complete.mar"))
            self.failUnless(not os.path.exists("./test-dest/unsigned/win32/hello.partial.mar"))
            self.failUnless(not os.path.exists("./test-dest/unsigned/win32/hello.checksums"))
            self.failUnless(not os.path.exists("./test-dest/unsigned/win32/hello.asc"))
            self.failUnless(os.path.exists("./test-dest/unsigned/win32/foo/hello.complete.mar"))
        finally:
            # clean up
            if os.path.isdir("./test-download"):
                shutil.rmtree("./test-download")
            if os.path.isdir("./test-dest"):
                shutil.rmtree("./test-dest")


if __name__ == '__main__':
    from unittest import main
    main()
