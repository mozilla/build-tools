from unittest import TestCase
import tempfile
import shutil
import os

from clobberer import do_clobber
from clobberer import get_clobber_times, legacy_get_clobber_times


class TestClobbererClient(TestCase):
    def setUp(self):
        self.outer_dir = tempfile.mkdtemp()
        os.chdir(self.outer_dir)  # replicating client logic

    def tearDown(self):
        shutil.rmtree(self.outer_dir)

    def test_do_clobber(self):
        file_name = 'my-name-is-mud'
        inner_dir = tempfile.mkdtemp(dir=self.outer_dir)
        open(os.path.join(self.outer_dir, file_name), 'a').close()
        self.assertTrue(os.path.exists(self.outer_dir))
        self.assertTrue(os.path.exists(inner_dir))
        self.assertTrue(os.path.exists(file_name))
        do_clobber(self.outer_dir)
        self.assertFalse(os.path.exists(inner_dir))
        self.assertFalse(os.path.exists(file_name))
        self.assertTrue(os.path.exists(self.outer_dir))

    def test_do_clobber_with_skip(self):
        skip_dir_name = 'muddy-mud-skipper'
        skip_file_name = 'powdered-toast'
        inner_dir = tempfile.mkdtemp(dir=self.outer_dir)
        open(os.path.join(self.outer_dir, skip_file_name), 'a').close()
        os.mkdir(os.path.join(self.outer_dir, skip_dir_name))
        self.assertTrue(os.path.exists(inner_dir))
        self.assertTrue(os.path.exists(skip_dir_name))
        self.assertTrue(os.path.exists(skip_file_name))
        do_clobber(self.outer_dir, skip=[skip_dir_name, skip_file_name])
        self.assertFalse(os.path.exists(inner_dir))
        self.assertTrue(os.path.exists(skip_dir_name))
        self.assertTrue(os.path.exists(skip_file_name))
        os.rmdir(skip_dir_name)
        os.remove(skip_file_name)

    def test_get_clobber_times(self):
        import urllib2
        import json

        builddir = 'the-roadhouse'
        timestamp = 9999
        who = 'JimMorrison@thedoors.net'
        fake_data = {'result': [
            {
                'builddir': builddir,
                'lastclobber': timestamp,
                'who': who,
                'slave': None
                }
            ]
        }
        FAKE_URLOPEN_DATA = json.dumps(fake_data)

        class FakeURLOpen(object):

            def __init__(self, *args, **kwargs):
                pass

            def read(self):
                # some fake clobber data
                return FAKE_URLOPEN_DATA

        # monkey patch urllib2 to force simulated clobber data
        urllib2.urlopen = FakeURLOpen

        clobber_dates_return = get_clobber_times('clobberer/lastclobber/all')
        self.assertEqual(clobber_dates_return, fake_data)

        # make sure it can handle no data
        fake_data_null = {'result': []}
        FAKE_URLOPEN_DATA = json.dumps(fake_data_null)
        clobber_dates_return = get_clobber_times('clobberer/lastclobber/all')
        self.assertEqual(clobber_dates_return, fake_data_null)

    def test_legacy_get_clobber_times(self):
        import urllib2
        lastclobber_fmt = '{}:{}:{}\n'
        builddir = 'the-roadhouse'
        timestamp = 9999
        who = 'JimMorrison@thedoors.net'
        FAKE_URLOPEN_DATA = lastclobber_fmt.format(builddir, timestamp, who)

        class FakeURLOpen(object):

            def __init__(self, *args, **kwargs):
                pass

            def read(self):
                # some fake clobber data
                return FAKE_URLOPEN_DATA

        # monkey patch urllib2 to force simulated clobber data
        urllib2.urlopen = FakeURLOpen

        clobber_dates_return = legacy_get_clobber_times(
            'clobberer/lastclobber',
            'branch',
            'buildername',
            'builddir',
            'slave',
            'master',
        )

        self.assertEqual(
            clobber_dates_return,
            {
                'result': [{
                    'builddir': builddir,
                    'lastclobber': timestamp,
                    'who': who,
                    'slave': None
                }]
            }
        )

        # make sure it can handle no data
        FAKE_URLOPEN_DATA = ""
        clobber_dates_return = legacy_get_clobber_times(
            'clobberer/lastclobber',
            'branch',
            'buildername',
            'builddir',
            'slave',
            'master',
        )
        self.assertEqual(clobber_dates_return, {'result': []})

if __name__ == '__main__':
    import unittest
    unittest.main()
