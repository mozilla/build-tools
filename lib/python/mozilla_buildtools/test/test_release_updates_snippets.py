import mock
import unittest

from release.platforms import ftp_update_platform_map
from release.updates.snippets import createSnippet, getSnippetPaths, SnippetError


class TestCreateSnippet(unittest.TestCase):
    def testSchema1(self):
        expected = """\
version=1
type=partial
url=http://bar
hashFunction=SHA512
hashValue=aaaaa
size=5
build=6
appv=4
extv=2
detailsUrl=http://details\n"""
        got = createSnippet(
            schema=1, type_='partial', url='http://bar', hash_='aaaaa', size=5,
            buildid=6, displayVersion='4', appVersion='2', detailsUrl='http://details')
        self.assertEquals(got, expected)

    def testSchema2(self):
        expected = """\
version=2
type=complete
url=http://foo
hashFunction=SHA512
hashValue=xxxxx
size=123
build=789
displayVersion=1 Beta 1
appVersion=1
platformVersion=1
detailsUrl=http://details\n"""
        got = createSnippet(
            schema=2, type_='complete', url='http://foo', hash_='xxxxx', size=123,
            buildid=789, displayVersion='1 Beta 1', appVersion=1, detailsUrl='http://details')
        self.assertEquals(got, expected)

    def testSchema2OptionalAttribute(self):
        expected = """\
version=2
type=complete
url=http://foo
hashFunction=SHA512
hashValue=xxxxx
size=123
build=789
displayVersion=1 Beta 1
appVersion=1
platformVersion=1
detailsUrl=http://details
actions=silent
billboardURL=http://billboard\n"""
        got = createSnippet(
            schema=2, type_='complete', url='http://foo', hash_='xxxxx', size=123,
            buildid=789, displayVersion='1 Beta 1', appVersion=1, detailsUrl='http://details', actions=['silent'],
            billboardURL='http://billboard')
        self.assertEquals(got, expected)

    def testDifferentHashFunction(self):
        expected = """\
version=2
type=complete
url=http://foo
hashFunction=SHA1024
hashValue=yyyyy
size=123
build=789
displayVersion=1 Beta 1
appVersion=1
platformVersion=1
detailsUrl=http://details\n"""
        got = createSnippet(
            schema=2, type_='complete', url='http://foo', hash_='yyyyy', size=123,
            buildid=789, displayVersion='1 Beta 1', appVersion=1, detailsUrl='http://details', hashFunction='SHA1024')
        self.assertEquals(got, expected)

    def testInvalidOptionalAttribute(self):
        self.assertRaises(
            SnippetError, createSnippet, 2, 1, 1, 1, 1, 1, 1, 1, 1, foo='bar')


class TestGetSnippetPaths(unittest.TestCase):
    def testOnePlatform(self):
        with mock.patch.dict(ftp_update_platform_map, {'p': ['pp']}):
            expected = ['foo/1/pp/2/aa/c/complete.txt']
            got = getSnippetPaths(
                product='foo', version='1', platform='p', buildid=2,
                locale='aa', channel='c', type_='complete')
            self.assertEquals(got, expected)

    def testMultiplePlatforms(self):
        with mock.patch.dict(ftp_update_platform_map, {'p': ['pp1', 'pp2']}):
            expected = ['foo/1/pp1/2/bb/c/partial.txt',
                        'foo/1/pp2/2/bb/c/partial.txt']
            got = getSnippetPaths(
                product='foo', version='1', platform='p', buildid=2,
                locale='bb', channel='c', type_='partial')
            self.assertEquals(got, expected)

    def testBadPlatform(self):
        self.assertRaises(SnippetError, getSnippetPaths, 'foo',
                          'foo', 'foo', 'foo', 1, 'foo', 'complete')
