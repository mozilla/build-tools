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

from buildbot.status.web import baseweb, base
from buildbot.status.web.waterfall import WaterfallStatusResource
from buildbot.status.web.builder import BuildersResource
from buildbot.status.web.slaves import BuildSlavesResource
from buildbot.status.web.changes import ChangesResource
from buildbot.status.web.about import AboutBuildbot
from buildbot.status.base import StatusReceiverMultiService
from buildbot.sourcestamp import SourceStamp
from buildbot.process.base import BuildRequest

from mako.template import Template
from twisted.python import log
from twisted.web.util import Redirect
import os.path
import urllib
import time
from datetime import datetime
from ConfigParser import ConfigParser

from buildbotcustom.status import stats
import simplejson

dummycontent = '''<h1>Comparisons</h1>
The best way to find comparisons is to go through the <a href="waterfall">waterfall</a> or the <a href="/dashboard/">Dashboard</a>.'''

class CompareBuild(base.HtmlResource):
  def __init__(self, template, build_status):
    base.HtmlResource.__init__(self)
    self.template = template
    self.build_status = build_status
  def content(self, req):
    result = self.build_status.getProperty('compare-result')
    summary = self.build_status.getProperty('coverage-result')
    build = dict()
    for k in ['locale', 'app', 'buildername', 'buildnumber']:
      build[k] = self.build_status.getProperty(k)
    startTime = round(self.build_status.getTimes()[0])
    build['starttime'] = datetime.utcfromtimestamp(startTime)
    return self.template.render(result=result, summary=summary, build=build)

class CompareBuilder(base.HtmlResource):
  title = "Compares for a builder"
  def __init__(self, template, builder_status):
    base.HtmlResource.__init__(self)
    self.template = template
    self.builder_status = builder_status
  def body(self, req):
    return dummycontent
  def getChild(self, path, req):
    try:
      num = int(path)
    except ValueError:
      return baseweb.HtmlResource.getChild(self, path, req)
    build_status = self.builder_status.getBuild(num)
    return CompareBuild(self.template, build_status)

class Comparisons(base.HtmlResource):
  title = "Comparison"
  def __init__(self):
    base.HtmlResource.__init__(self)
    path = __file__[:__file__.rfind('l10n.py')-1]
    self.template = Template(filename=os.path.join(path, 'compare.mako'),
                             output_encoding='utf-8',
                             encoding_errors='replace')
    log.msg('Comparison resource started')
  def loadTemplate(self, path):
    return
    self.template = Template(filename=os.path.join(path, 'compare.mako'),
                             output_encoding='utf-8',
                             encoding_errors='replace')
  def body(self, req):
    return dummycontent
  def getChild(self, path, req):
    s = self.getStatus(req)
    if path in s.getBuilderNames():
      builder_status = s.getBuilder(path)
      return CompareBuilder(self.template, builder_status)

    return base.HtmlResource.getChild(self, path, req)

class ForceL10n(base.HtmlResource):
  title = "Force l10n builds"
  my_js = '''<script type="application/javascript">
var trees = %s;
function onSelectTree(elem) {
  var tree = trees[elem.value];
  document.getElementById('app').value = tree.app;
  var tmpl = '<input name="builders" type="checkbox" value="BUILDER" checked>BUILDER<br>\\n';
  var inner = '';
  for (var i in tree.builders) {
    inner += tmpl.replace(new RegExp('BUILDER', 'g'), tree.builders[i]);
  }
  document.getElementById('builders').innerHTML = inner;
};
</script>
'''
  def __init__(self):
    base.HtmlResource.__init__(self)
    cp = ConfigParser()
    cp.read('l10nbuilds.ini')
    self.trees = dict()
    for section in cp.sections():
      self.trees[section] = dict(app = cp.get(section, 'app'),
                                 locales = cp.get(section, 'locales').split(),
                                 builders = cp.get(section, 'builders').split())
    self.template = None
  def head(self, req):
    return self.my_js % simplejson.dumps(self.trees);
  def body(self, req):
    content = '''<form method="POST" action="#">
  <p>Trees:</p>'''
    for tree in self.trees.keys():
      content += '<input name="tree" type="radio" size="30" value="%(tree)s" onclick="onSelectTree(this)">%(tree)s<br>' % dict(tree = tree)
    content += '''<input name="app" type="hidden" id="app">
  <p>Builders:</p>
  <p id="builders"></p>
  Locales: <input name="locales" type="text" size="30"><br>
  <input type="submit" value="Force">
'''
    return content
  def render(self, req):
    if req.method == "POST":
      return self.force(req)
    return base.HtmlResource.render(self, req)
  def force(self, req):
    c = self.getControl(req)
    tree = req.args.get('tree', [''])[0]
    app = req.args.get('app', [''])[0]
    locales = req.args.get('locales', [''])[0]
    builders = req.args.get('builders', [''])[0]
    locales = locales.split()
    builders = builders.split()
    r = "%s %s (forced)"
    s = SourceStamp()
    log.msg("forcing " + ', '.join(locales) + " on " + app)
    count = 0
    for locale in locales:
      for builder in builders:
        req = BuildRequest(r % (tree, locale), s, builderName = builder)
        req.properties.update(dict(app=app,
                                   locale=locale,
                                   tree=tree,
                                   needsCheckout=True), "Forced")
        try:
          bc = c.getBuilder(builder)
          bc.requestBuildSoon(req)
        except Exception, e:
          log.msg("failed to force build, " + str(e))
        count += 1
    return "Forced %i builds" % count
  

class WebStatus(baseweb.WebStatus):
  def setupUsualPages(self):
    self.putChild("waterfall", WaterfallStatusResource())
    self.putChild("builders", BuildersResource()) # has builds/steps/logs
    self.putChild("changes", ChangesResource())
    self.putChild("buildslaves", BuildSlavesResource())
    self.putChild("about", AboutBuildbot())
    self.comparisons = Comparisons()
    self.putChild("compare", self.comparisons)
    self.putChild("statistics", stats.StatsResource())
    if self.allowForce:
      self.putChild("force-l10n", ForceL10n())
  def setupSite(self):
    htmldir = os.path.join(self.parent.basedir, "public_html")
    self.comparisons.loadTemplate(htmldir)
    baseweb.WebStatus.setupSite(self)

import simplejson
from buildbot.status.builder import Results
from buildbotcustom.status.l10ndb import Build, Active, session

def addBuild(buildstatus):
  try:
    b = Build(buildstatus)
  except Exception, e:
    log.msg("Creating build database object raised " + str(e))
    return
  session.save(b)
  session.commit()
  # check if we need to add this to our active table
  aq = session.query(Active)
  if aq.filter_by(**b.dict()).count():
    # we already have this one
    return
  a = Active(b)
  session.save(a)
  session.commit()
    

class LatestL10n(StatusReceiverMultiService):
  def __init__(self, builders):
    StatusReceiverMultiService.__init__(self)
    self.builders = builders
  def buildFinished(self, builderName, build, results):
    if builderName not in self.builders:
      # we don't listen to this one
      return
    log.msg("LatestL10n getting notified")
    # notify db
    addBuild(build)
    # db done, now try update json
    props = {}
    try:
      for key in ['tree', 'locale', 'app', 'coverage-result', 'buildnumber', 'buildername', 'slavename']:
        props[key] = build.getProperty(key)
    except KeyError:
      log.msg('reported build not proper, %s is missing' % key)
      return
    coverage = props.pop('coverage-result')
    for k, v in coverage.iteritems():
      props['coverage_' + k] = v
    props['result'] = Results[results]
    starttime, endtime = self.getTimes(build)
    props.update(dict(starttime=starttime, endtime=endtime))
    status = dict(items=[])
    try:
      status = simplejson.load(open(self.json))
    except Exception:
      pass
    items = status['items']
    rv = dict(props)
    id = '/'.join((builderName, props['tree'], props['app'], props['locale']))
    rv['id'] = id
    rv['label'] = props['locale']
    rv['type'] = 'Build'
    needsAppend = True
    for item in items:
      if item['id'] == id:
        item.clear()
        item.update(rv)
        needsAppend = False
        break
    if needsAppend:
      items.append(rv)
    simplejson.dump(dict(items=items), open(self.json, 'w'))
    log.msg("wrote out %s with %d items" % (self.json, len(items)))
  def builderAdded(self, name, builder):
    log.msg("subscribing to " + name)
    return self
  def setServiceParent(self, parent):
    StatusReceiverMultiService.setServiceParent(self, parent)
    self.setup()
  def setup(self):
    self.json = os.path.join(self.parent.basedir, "public_html",
                             "l10n_status.js")
    self.status = self.parent.getStatus()
    self.status.subscribe(self)
    log.msg("LatestL10n subscribing")
  def disownServiceParent(self):
    self.status.unsubscribe(self)
    return base.StatusReceiverMultiService.disownServiceParent(self)
  def getTimes(self, status):
    def toISO8601(t):
      return datetime.utcfromtimestamp(round(t)).isoformat() + 'Z'
    return map(toISO8601, status.getTimes())
