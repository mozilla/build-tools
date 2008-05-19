

# test step.ShellCommand and the slave-side commands.ShellCommand

import sys, time, os
from twisted.trial import unittest
from twisted.internet import reactor, defer
from twisted.python import util, log
from buildbotcustom.slave.comparestep import CompareCommand
from buildbot.test.runutils import SlaveCommandTestBase
from shutil import copytree
import pdb

def createStage(basedir, *files):
    '''Create a staging environment in the given basedir

    Each argument is a tuple of
    - a tuple with path segments
    - the content of the file to create
    '''
    for pathsteps, content in files:
        try:
            os.makedirs(os.path.join(basedir, *pathsteps[:-1]))
        except OSError, e:
            if e.errno != 17:
                raise e
        f = open(os.path.join(basedir, *pathsteps), 'w')
        f.write(content)
        f.close()


class SlaveSide(SlaveCommandTestBase, unittest.TestCase):
    basedir = "test_compare.testSuccess"
    stageFiles = ((('mozilla', 'client.mk'),
                     '''echo-variable-LOCALES_app:
\t@echo app
'''),
                  (('mozilla','app','locales','en-US','dir','file.dtd'),
                   '<!ENTITY test "value">\n<!ENTITY test2 "value2">\n'),
                  (('l10n','good','app','dir','file.dtd'),
                   '''
<!ENTITY test "local value">
<!ENTITY test2 "local value2">
'''),
                  (('l10n','obsolete','app','dir','file.dtd'),
                   '''
<!ENTITY test "local value">
<!ENTITY test2 "local value 2">
<!ENTITY test3 "local value 3">
'''),
                  (('l10n','missing','app','dir','file.dtd'),
                   '<!ENTITY test "local value">\n'))
    def setUp(self):
        self.setUpBuilder(self.basedir)
        createStage(self.basedir, *self.stageFiles)

    def testGood(self):
        args = {
            'application': "app",
            'locale': "good",
            'workdir': ".",
            }
        d = self.startCommand(CompareCommand, args)
        d.addCallback(self._check,
                      0,
                      dict(),
                      dict(completion=100))
        return d

    def testObsolete(self):
        args = {
            'application': "app",
            'locale': "obsolete",
            'workdir': ".",
            }
        d = self.startCommand(CompareCommand, args)
        d.addCallback(self._check,
                      1,
                      None,
                      dict(completion=100))
        return d

    def testMissing(self):
        args = {
            'application': "app",
            'locale': "missing",
            'workdir': ".",
            }
        d = self.startCommand(CompareCommand, args)
        d.addCallback(self._check,
                      2,
                      None,
                      dict(completion=50))
        return d

    def _check(self, res, expectedRC, expectedDetails, exSummary):
        self.assertEqual(self.findRC(), expectedRC)
        res = self._getResults()
        details = res['details']
        summary = res['summary']
        if expectedDetails is not None:
            self.assertEquals(details, dict())
        for k, v in exSummary.iteritems():
            self.assertEquals(summary[k], v)
        return

    def _getResults(self):
        rv = dict()
        for d in self.builder.updates:
            if 'result' in d:
                rv.update(d['result'])
        return rv
