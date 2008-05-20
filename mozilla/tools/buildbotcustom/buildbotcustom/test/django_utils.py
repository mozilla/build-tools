# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is l10n test automation.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation
# Portions created by the Initial Developer are Copyright (C) 2008
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#	Axel Hecht <l10n@mozilla.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

"""Base classes for buildbot/django integration tests.

This module provides base classes for testing the integration of buildbot
and the django status database models.
"""

from datetime import datetime

from twisted.trial import unittest
from twisted.internet import defer, reactor

from buildbot import interfaces
from buildbot.changes import changes
from buildbot.sourcestamp import SourceStamp
from buildbot.test.runutils import RunMixin

from django.conf import settings, UserSettingsHolder, global_settings
settings._target = UserSettingsHolder(global_settings)
settings.DATABASE_ENGINE = 'sqlite3'
settings.INSTALLED_APPS = (
  'buildbotcustom.builds',
)

from django.test.utils import create_test_db, destroy_test_db
from buildbotcustom.builds.models import *

class DjangoBuildTestCase(unittest.TestCase, RunMixin):
  """Base class that provides basic test setup and tear down for the
  django db layer by creating a test database for the INSTALLED_APPS.
  """
  old_name = settings.DATABASE_NAME
  config = None
  def setUp(self):
    self._db = create_test_db()
    return RunMixin.setUp(self)

  def tearDown(self):
    destroy_test_db(self.old_name)
    return RunMixin.tearDown(self)

  def buildSubmitted(self):
    pass
  def buildDone(self):
    pass
  def allBuildsDone(self):
    pass


class BuildQueue(DjangoBuildTestCase):
  """Base class for tests that want to submit one forced build
  after the other.

  Entry point for the tests is testBuild, calling into _doBuild,
  followed by a waitUntilBuilder calling into _doneBuilding.
  That in turn calls back into _doBuild, which stops once there are
  no more requests.
  """
  requests = 1
  def testBuild(self):
    m = self.master
    s = m.getStatus()
    self.assert_(self.config is not None)
    m.loadConfig(self.config)
    m.readConfig = True
    m.startService()
    d = self.connectSlave(builders=["dummy"])
    d.addCallback(self._doBuild, xrange(self.requests))
    return d

  def _doBuild(self, res, requests_iter):
    try:
      requests_iter.next()
    except StopIteration:
      self.allBuildsDone()
      return
    deferreds = []
    deferreds.append(self.requestBuild("dummy"))
    deferreds.append(self.master.botmaster.waitUntilBuilderIdle("dummy"))
    dl = defer.DeferredList(deferreds)
    self.buildSubmitted()
    dl.addCallback(self._doneBuilding, requests_iter)
    return dl

  def _doneBuilding(self, res, requests_iter):
    self.buildDone()
    return self._doBuild(res, requests_iter)


class Request(object):
  """Helper object for TimedChangesQueue, representing changes and the
  delay when to submit them to the master.
  """
  def __init__(self, delay=0, files='', who='John Doe', when=0, comment=''):
    self.delay = delay
    self.files = None
    if files:
      self.files = files.split('\n')
    self.when = when
    self.who = who
    self.comment = comment
  def change(self):
    return changes.Change(self.who, self.files, self.comment, when = self.when)
  def datetime(self):
    return datetime.utcfromtimestamp(self.when)


class TimedChangesQueue(DjangoBuildTestCase):
  """Base class for tests that want to submit changes to the fake master
  and check the results after that.

  The requests are Request objects describing the change and the delay for
  this change.

  The entry point is testBuild, which fires _doBuild. This builds up a
  chain of calls into reactor.callLater and control.addChange, followed
  by a waitUntilBuilderIdle. The call into that is done after the last
  change is submitted, so we can actually have idle times during the
  sequence of builds.

  CAVEATS:
  - The scheduler needs to trigger builds immediately, i.e., no timeout.
  Otherwise, we can't figure out if there was just no build, or if it's
  not started yet.
  - This only calls back into allBuildsDone at the end, there is no 
  notification for individual builds. You'd have to add your own status
  handler for that.
  """
  requests = (
    Request(when = 1200000000),
  )
  def testBuild(self):
    """Entry point for trial.unittest.TestCase"""
    m = self.master
    self.assert_(self.config is not None)
    m.loadConfig(self.config)
    m.readConfig = True
    m.startService()
    d = self.connectSlave(builders=["dummy"])
    d.addCallback(self._doBuild, iter(self.requests))
    return d

  def _doBuild(self, res, requests_iter):
    """Helper called after slave connected."""
    def verboseCallback(res, msg, method, *args):
      """Internal helper, dropping the callback result."""
      #print msg, args
      method(*args)

    final = d = d2 = defer.Deferred()
    for request in reversed(self.requests):
      d = d2
      d.addCallback(verboseCallback, "calling addChange",
                    self.control.addChange, request.change())
      d2 = defer.Deferred()
      d2.addCallback(verboseCallback, "starting callLater", 
                     reactor.callLater, request.delay, d.callback, None)
    def idlecb(res):
      """Callback to call into after all changes are submitted to wait
      for idle.
      """
      #print "idlecb called"
      d = self.master.botmaster.waitUntilBuilderIdle('dummy')
      d.addCallback(self._doneBuilding)
      return d
    final.addCallback(idlecb)
    d2.callback(None)
    return final

  def _doneBuilding(self, res):
    """twisted callback for waitUntilBuilderIdle

    Calls subclassed allBuildsDone().
    """
    self.allBuildsDone()
