try:
    # Python 2.6 backport with assertDictEqual()
    import unittest2 as unittest
except ImportError:
    import unittest
from balrog.submitter.cli import NightlySubmitterBase, NightlySubmitterV4
from balrog.submitter.updates import merge_partial_updates

class TestNightlySubmitterBase(unittest.TestCase):

    def test_replace_canocical_url(self):
        url_replacements = [
            ("ftp.mozilla.org", "download.cdn.mozilla.net")
        ]
        submitter = NightlySubmitterBase(api_root=None, auth=None,
                                         url_replacements=url_replacements)
        self.assertEqual(
            'http://download.cdn.mozilla.net/pub/mozilla.org/some/file',
            submitter._replace_canocical_url(
                'http://ftp.mozilla.org/pub/mozilla.org/some/file')
        )


class TestNightlySubmitterV4(unittest.TestCase):

    def test_canonical_ur_replacement(self):
        url_replacements = [
            ("ftp.mozilla.org", "download.cdn.mozilla.net")
        ]
        submitter = NightlySubmitterV4(api_root=None, auth=None,
                                       url_replacements=url_replacements)
        completeInfo = [{
            'size': 123,
            'hash': 'abcd',
            'url': 'http://ftp.mozilla.org/url'
        }]
        data = submitter._get_update_data("prod", "brnch", completeInfo)
        self.assertDictEqual(
            data,
            {'completes': [{
                'fileUrl': 'http://download.cdn.mozilla.net/url',
                'filesize': 123,
                'from': '*',
                'hashValue': 'abcd'
            }]})

    def test_no_canonical_ur_replacement(self):
        submitter = NightlySubmitterV4(api_root=None, auth=None,
                                       url_replacements=None)
        completeInfo = [{
            'size': 123,
            'hash': 'abcd',
            'url': 'http://ftp.mozilla.org/url'
        }]
        data = submitter._get_update_data("prod", "brnch", completeInfo)
        self.assertDictEqual(
            data,
            {'completes': [{
                'fileUrl': 'http://ftp.mozilla.org/url',
                'filesize': 123,
                'from': '*',
                'hashValue': 'abcd'
            }]})


class TestUpdateMerger(unittest.TestCase):
    # print the diff between large dicts
    maxDiff = None

    def test_merge_updates(self):
        old_data = {
            'some_other_field': "123",
            'some_other_field2': {"a": "b", "c": 1},
            'some_other_list': [1, 2, 3],
            'completes': [
                {
                    'fileUrl': 'https://complete1',
                    'filesize': 123,
                    'from': '*',
                    'hashValue': '123abcdef'
                },
            ],
            'partials': [
                {
                    'fileUrl': 'https://partial1',
                    'filesize': 111,
                    'from': '111',
                    'hashValue': '123abc'
                },
                {
                    'fileUrl': 'https://partial2',
                    'filesize': 112,
                    'from': '112',
                    'hashValue': '223abc'
                },
            ]
        }
        new_data = {
            'completes': [
                {
                    'fileUrl': 'https://complete2',
                    'filesize': 122,
                    'from': '*',
                    'hashValue': '122abcdef'
                },
            ],
            'partials': [
                {
                    'fileUrl': 'https://partial2/differenturl',
                    'filesize': 112,
                    'from': '112',
                    'hashValue': '223abcd'
                },
                {
                    'fileUrl': 'https://partial3',
                    'filesize': 113,
                    'from': '113',
                    'hashValue': '323abc'
                },
            ]
        }
        merged = merge_partial_updates(old_data, new_data)
        expected_merged = {
            'some_other_field': "123",
            'some_other_field2': {"a": "b", "c": 1},
            'some_other_list': [1, 2, 3],
            'completes': [
                {
                    'fileUrl': 'https://complete2',
                    'filesize': 122,
                    'from': '*',
                    'hashValue': '122abcdef'
                },
            ],
            'partials': [
                {
                    'fileUrl': 'https://partial1',
                    'filesize': 111,
                    'from': '111',
                    'hashValue': '123abc'
                },
                {
                    'fileUrl': 'https://partial2/differenturl',
                    'filesize': 112,
                    'from': '112',
                    'hashValue': '223abcd'
                },
                {
                    'fileUrl': 'https://partial3',
                    'filesize': 113,
                    'from': '113',
                    'hashValue': '323abc'
                },
            ]
        }
        self.assertDictEqual(merged, expected_merged)
