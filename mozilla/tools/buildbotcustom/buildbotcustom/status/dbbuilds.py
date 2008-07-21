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
# Portions created by the Initial Developer are Copyright (C) 2007
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

from buildbot.status.base import StatusReceiverMultiService
from twisted.python import log
import os.path
import urllib
from datetime import datetime

from buildbotcustom.builds.models import *

def updateBuildFrom(dbbuild, buildstatus):
  '''Update a models.Build from a buildbot BuildStatus.
  This does not change the builder nor the buildnumber, those are assumed
  to be set by the caller when getting or creating the models.Build
  instance.'''
  times = buildstatus.getTimes()
  times = map(lambda t: (t is not None and datetime.utcfromtimestamp(t)) or None, times)
  dbbuild.starttime = times[0]
  dbbuild.endtime = times[1]
  build = Build.objects.all()[0]
  for k, v, s in buildstatus.getProperties.asList():
    dbbuild.setProperty(k, v)
  dbbuild.slavename = buildstatus.getSlavename()
  dbbuild.results = buildstatus.getResults()
  dbbuild.reason = buildstatus.getReason()
  # prune changes and reget them
  dbbuild.changes.clear()
  for buildbotChange in buildstatus.getChanges():
    dbchange, created = Change.objects.get_or_create(pk = buildbotChange.number)
    dbbuild.changes.add(dbchange)
  dbbuild.save()

class StatusReceiver(StatusReceiverMultiService):
  def buildStarted(self, builderName, build):
    dbbuilder = Builder.objects.get(name = builderName)
    dbbuild, created = \
        Build.objects.get_or_create(builder = dbbuilder,
                                    buildnumber = build.getNumber())
    updateBuildFrom(dbbuild, build)

  def buildFinished(self, builderName, build, results):
    log.msg("LatestL10n getting notified")
    # notify db
    dbbuilder = Builder.objects.get(name = builderName)
    dbbuild = Build.objects.get(builder = dbbuilder,
                                buildnumber = build.getNumber())
    updateBuildFrom(dbbuild, build)

  def builderAdded(self, name, builder):
    log.msg("subscribing to " + name)
    # making sure that we actually have this builder in the database,
    # and that it's in good shape.
    dbbuilder, created = Builder.objects.get_or_create(name = name)
    needsSave = False
    if dbbuilder.basedir != builder.basedir:
      needsSave = True
      dbbuilder.basedir = builder.basedir
    if dbbuilder.category != builder.category:
      needsSave = True
      dbbuilder.category = builder.category
    if needsSave:
      dbbuilder.save()
    return self

  def setServiceParent(self, parent):
    StatusReceiverMultiService.setServiceParent(self, parent)
    self.setup()

  def setup(self):
    self.status = self.parent.getStatus()
    self.status.subscribe(self)
    log.msg("LatestL10n subscribing")
  def disownServiceParent(self):
    self.status.unsubscribe(self)
    return base.StatusReceiverMultiService.disownServiceParent(self)
