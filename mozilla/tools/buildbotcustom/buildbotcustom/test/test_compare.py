

# test step.ShellCommand and the slave-side commands.ShellCommand

import sys, time, os
from twisted.trial import unittest
from twisted.internet import reactor, defer
from twisted.python import util, log
from buildbotcustom.slave.comparestep import CompareCommand
from buildbot.test.runutils import SlaveCommandTestBase
from shutil import copytree
import pdb

class SlaveSide(SlaveCommandTestBase, unittest.TestCase):
    def testCompareCommand(self):
        basedir = "test_compare.testOne"
        self.setUpBuilder(basedir)
        # copy our own working dir into the sandbox
        repbase = __file__[:__file__.rfind('mozilla')]
        for mod in ['mozilla', 'l10n']:
            copytree(repbase + mod, basedir + '/' + mod)
        args = {
            'application': "app",
            'locale': "partial",
            'workdir': ".",
            }
        finishd = self.startCommand(CompareCommand, args)
        self._check_timeout = 10
        d = self._check_and_wait()
        def _wait_for_finish(res, finishd):
            return finishd
        d.addCallback(_wait_for_finish, finishd)
        d.addCallback(self.collectUpdates)
        def _check(logs):
            self.assertEqual(logs, {'header': 'Comparing partial against en-US for .\n', 'result': 'observer'})
            return
        d.addCallback(_check)
        d.addBoth(self._maybePrintError)
        return d

    def _check_and_wait(self, res=None):
        self._check_timeout -= 1
        if self._check_timeout <= 0:
            raise defer.TimeoutError("gave up on command")
        logs = self.collectUpdates()
        if not self.cmd.running:
            return
        spin = defer.Deferred()
        spin.addCallback(self._check_and_wait)
        reactor.callLater(1, spin.callback, None)
        return spin

    def _maybePrintError(self, res):
        rc = self.findRC()
        if rc != 0:
            print "Command ended with rc=%s" % rc
            print "STDERR:"
            self.printStderr()
        return res

    def collectUpdates(self, res=None):
        logs = {}
        for u in self.builder.updates:
            for k in u.keys():
                if k == "log":
                    logname,data = u[k]
                    oldlog = logs.get(("log",logname), "")
                    logs[("log",logname)] = oldlog + data
                elif k == "rc":
                    pass
                else:
                    logs[k] = logs.get(k, "") + str(u[k])
        return logs

class Other(unittest.TestCase):
    def test_misc(self):
        self.assertEqual('foo','foo')
