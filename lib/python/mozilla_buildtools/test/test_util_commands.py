import unittest
import subprocess

from util.commands import run_cmd, get_output, run_cmd_periodic_poll


class TestRunCmd(unittest.TestCase):
    def testSimple(self):
        self.assertEquals(run_cmd(['true']), 0)

    def testFailure(self):
        self.assertRaises(subprocess.CalledProcessError, run_cmd, ['false'])

    def testOutput(self):
        output = get_output(['echo', 'hello'])
        self.assertEquals(output, 'hello\n')

    def testStdErr(self):
        output = get_output(
            ['bash', '-c', 'echo hello 1>&2'], include_stderr=True)
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


class TestRunCmdiPeriodicPoll(unittest.TestCase):

    def testSimple(self):
        self.assertEquals(run_cmd_periodic_poll(['true']), 0)

    def testFailure(self):
        self.assertRaises(subprocess.CalledProcessError, run_cmd_periodic_poll,
                          ['false'])

    def testSuccess2secs(self):
        self.assertEquals(
            run_cmd_periodic_poll(['bash', '-c', 'sleep 2 && true']),
            0)

    def testFailure2secs(self):
        self.assertRaises(
            subprocess.CalledProcessError, run_cmd_periodic_poll,
            ['bash', '-c', 'sleep 2 && false'])

    def testSuccess3secsWith2secsPoll(self):
        self.assertEquals(
            run_cmd_periodic_poll(['bash', '-c', 'sleep 3 && true'],
                                  warning_interval=2),
            0)

    def testSuccessCallback(self):
        self.callback_called = 0

        def callback(start_time, eapsed, proc):
            self.callback_called += 1

        run_cmd_periodic_poll(['bash', '-c', 'sleep 5 && true'],
                              warning_interval=2, warning_callback=callback),
        self.assertEqual(self.callback_called, 2)

    def testFailureCallback(self):
        self.callback_called = 0

        def callback(start_time, eapsed, proc):
            self.callback_called += 1

        self.assertRaises(
            subprocess.CalledProcessError, run_cmd_periodic_poll,
            ['bash', '-c', 'sleep 5 && false'], warning_interval=2,
            warning_callback=callback)
        self.assertEqual(self.callback_called, 2)
