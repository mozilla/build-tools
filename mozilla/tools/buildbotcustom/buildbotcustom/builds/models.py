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

'''Buildbot state database model

This module mirrors the buildbot status classes in django 
database-backed model classes.

Right now, everything between individual Builders and Changes is implemented.
That means, there is no model for the master, nor do Changes contain files
or author/time information yet.
'''

from django.db import models
import simplejson


class Change(models.Model):
  """Model for buildbot.changes.changes.Change.

  TODO: who, files, comments, when, branch, revision
  POSSIBLY: isdir, links
  """
  pass

class Property(models.Model):
  """Helper model for build properties.

  To support complex property values, they are internally stored in JSON.
  """
  name            = models.CharField(max_length=20, db_index=True)
  value           = models.TextField()
  unique_together = (('name', 'value'),)

  def __unicode__(self):
    return "%s: %s" % (self.name, self.value)


class Builder(models.Model):
  """Model for buildbot.status.builder.BuilderStatus"""
  name     = models.CharField(max_length=50, unique=True)
  basedir  = models.CharField(max_length=50, null=True)
  category = models.CharField(max_length=30, null=True)


class Build(models.Model):
  """Model for buildbot..status.builder.Build

  TODO: BuildSteps
  """
  buildnumber = models.IntegerField(null=True, db_index=True)
  properties  = models.ManyToManyField(Property, related_name = 'builds')
  builder     = models.ForeignKey(Builder, related_name = 'builds')
  slavename   = models.CharField(max_length=50, null=True)
  starttime   = models.DateTimeField(null=True)
  endtime     = models.DateTimeField(null=True)
  results     = models.IntegerField(null=True)
  reason      = models.CharField(max_length=50, blank=True, default='')
  changes     = models.ManyToManyField(Change, null=True,
                                       related_name = 'builds')

  def setProperty(self, name, value):
    value = simplejson.dumps(value)
    try:
      # First, see if we have the property, or a property of that name,
      # at least.
      prop = self.properties.get(name=name)
      if prop.value == value:
        # we already know this, we're done
        return
      if prop.builds.count() < 2:
        # this is our own property, set the new value
        prop.value = value
        prop.save()
        return
      # otherwise, unbind the property, and fake a DoesNotExist
      self.properties.remove(prop)
      raise Property.DoesNotExist(name)
    except Property.DoesNotExist:
      prop, created = Property.objects.get_or_create(name = name,
                                                     value = value)
    self.properties.add(prop)
    self.save()
  def getProperty(self, name):
    try:
      prop = self.properties.get(name = name)
    except Property.DoesNotExist:
      raise KeyError(name)
    return simplejson.loads(prop.value)

  def __unicode__(self):
    v = self.builder.name
    if self.buildnumber is not None:
      v += ': %d' % self.buildnumber
    return v
