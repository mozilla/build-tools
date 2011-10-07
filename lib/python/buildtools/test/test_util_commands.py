import unittest, subprocess

from util.commands import run_cmd, get_output

class TestRunCmd(unittest.TestCase):
    def testSimple(self):
        self.assertEquals(run_cmd(['true']), 0)

    def testFailure(self):
        self.assertRaises(subprocess.CalledProcessError, run_cmd, ['false'])

    def testOutput(self):
        output = get_output(['echo', 'hello'])
        self.assertEquals(output, 'hello\n')

    def testStdErr(self):
        output = get_output(['bash', '-c', 'echo hello 1>&2'], include_stderr=True)
        self.assertEquals(output, 'hello\n')

    def testNoStdErr(self):
        output = get_output(['bash', '-c', 'echo hello 1>&2'])
        self.assertEquals(output, '')

    def testBadOutput(self):
        self.assertRaises(subprocess.CalledProcessError, get_output, ['false'])

    def testOutputAttachedToError(self):
        """Older versions of CalledProcessError don't attach 'output' to
           themselves. This test is to ensure that get_output always does."""
        output = "nothing"
        try:
            get_output(['bash', '-c', 'echo hello && false'])
        except subprocess.CalledProcessError, e:
            self.assertEquals(e.output, 'hello\n')
        else:
            self.fail("get_output did not raise CalledProcessError")
