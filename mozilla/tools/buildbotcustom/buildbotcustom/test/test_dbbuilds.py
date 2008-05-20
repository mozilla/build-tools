from datetime import datetime, timedelta

from twisted.trial import unittest
from twisted.internet import defer

from buildbot import interfaces
from buildbot.test.runutils import RunMixin

from django.conf import settings, UserSettingsHolder, global_settings
settings._target = UserSettingsHolder(global_settings)
settings.DATABASE_ENGINE = 'sqlite3'
settings.INSTALLED_APPS = (
  'buildbotcustom.builds',
)


config = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
s = factory.s

f = factory.BuildFactory([
    s(dummy.Dummy, timeout=1),
    s(dummy.RemoteDummy, timeout=2),
    ])

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['builders'] = []
c['builders'].append({'name': 'dummy', 'slavename': 'bot1',
                      'builddir': 'dummy1', 'factory': f})
c['slavePortnum'] = 0
"""

config_2 = config + '''
from buildbotcustom.status.dbbuilds import StatusReceiver
c['status'] = [StatusReceiver()]
'''

from django.conf import settings
from django.test.utils import create_test_db, destroy_test_db
from buildbotcustom.builds.models import *

class DatabaseStatus(RunMixin, unittest.TestCase):
  old_name = settings.DATABASE_NAME
  def setUp(self):
    self._db = create_test_db()
    return RunMixin.setUp(self)

  def tearDown(self):
    destroy_test_db(self.old_name)
    return RunMixin.tearDown(self)

  def testBuild(self):
    m = self.master
    s = m.getStatus()
    m.loadConfig(config_2)
    m.readConfig = True
    m.startService()
    d = self.connectSlave(builders=["dummy"])
    d.addCallback(self._doBuild)
    return d

  def _doBuild(self, res):
    c = interfaces.IControl(self.master)
    d = self.requestBuild("dummy")
    d2 = self.master.botmaster.waitUntilBuilderIdle("dummy")
    dl = defer.DeferredList([d, d2])
    startedAround = datetime.utcnow()
    dl.addCallback(self._doneBuilding, startedAround)
    return dl

  def _doneBuilding(self, res, startedAround):
    endedAround = datetime.utcnow()
    delta = timedelta(0, 1)
    self.assertEquals(Build.objects.count(), 1)
    build = Build.objects.all()[0]
    self.assert_(abs(build.starttime-startedAround) < delta)
    self.assert_(abs(build.endtime-endedAround) < delta)
    self.assertEquals(build.getProperty('buildername'), 'dummy')
    self.assertEquals(build.getProperty('slavename'), 'bot1')
    self.assertEquals(build.getProperty('buildnumber'), 0)
    self.assertEquals(build.reason, 'forced build')
    self.assertEquals(build.changes.count(), 0)
    pass
