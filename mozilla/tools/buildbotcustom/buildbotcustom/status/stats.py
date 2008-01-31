from mako.template import Template
from pkg_resources import resource_string
from datetime import datetime, timedelta
from xml.dom.minidom import getDOMImplementation
import urllib

from buildbot.status.web import baseweb, base
from twisted.web.util import Redirect
from twisted.python import log
from sqlalchemy import select, and_

from buildbotcustom.status import l10ndb

statstemplate = Template(resource_string(__name__, 'stats_plot.mako'),
                         output_encoding='utf-8',
                         encoding_errors='replace')
pickertemplate = Template(resource_string(__name__, 'stats_picker.mako'),
                          output_encoding='utf-8',
                          encoding_errors='replace')

class StatsResource(base.HtmlResource):
  days = 30
  title = "Statistics"
  args = ['buildername', 'tree', 'app', 'locale']
  def __init__(self):
    self.builder = self.tree = self.app = self.locale = None
  def content(self, req):
    args = dict()
    for arg in self.args:
      if arg in req.args:
        args[arg] = req.args[arg]
    if not args:
      return self.renderPicker(req)
    clause = and_()
    for k, values in args.iteritems():
      clause.append(l10ndb.Active.c[k].in_(values))
    query = l10ndb.session.query(l10ndb.Active).filter(clause)
    if query.count() != 1:
      return self.renderPicker(req, args)
    build = query.first().dict()
    s = self.getStatus(req)
    builder_status = s.getBuilder(build['buildername'])
    
    return self.renderStats(builder_status, build['tree'], build['app'],
                            build['locale'])
  def renderPicker(self, req, args = None):
    return pickertemplate.render(args = args)
  def renderStats(self, builder, tree, app, locale):
    starttime = datetime.utcnow() - timedelta(self.days)
    eventdoc = getDOMImplementation().createDocument(None, 'data', None)
    eventdoc.documentElement.setAttribute('date-time-format', 'iso8601')
    statrows = []
    startcol = l10ndb.Build.starttime

    q = l10ndb.q.filter_by(tree = tree,
                           app = app,
                           locale = locale)
    for b in q.filter(startcol > starttime).order_by(startcol):
      statrows.append(dict(missing = b.c_missing + b.c_missingInFiles,
                           obsolete = b.c_obsolete,
                           unchanged = b.c_unchanged,
                           time = b.starttime.isoformat() + 'Z'))
      if not b.l10nchange:
        # only add localizer changes to the events
        continue
      build = builder.getBuild(b.buildnumber)
      e = eventdoc.createElement('event')
      e.setAttribute('start', b.starttime.isoformat() + 'Z')
      e.setAttribute('title', ', '.join(build.getResponsibleUsers()))
      e.setAttribute('link', self.getBonsai(b.starttime, b.locale))
      eventdoc.documentElement.appendChild(e)
      comments = '\n'.join([c.comments for c in build.getChanges()])
      e.appendChild(eventdoc.createTextNode('<pre>%s</pre>' % comments))
    return statstemplate.render(rows=statrows, events = eventdoc,
                             buildername = builder.getName(),
                             tree = tree, app = app, locale = locale)

  def getBonsai(self, d, loc):
    burl = 'http://bonsai-l10n.mozilla.org/cvsquery.cgi?treeid=default&module=all&sortby=Date&date=explicit&cvsroot=%2Fl10n&dir=l10n/' + loc + '&'
    half = timedelta(hours=.5)
    return burl + 'mindate=%sZ&maxdate=%sZ' % \
        ((d-half).isoformat(),(d+half).isoformat())


if __name__=='__main__':
  r = StatsResource()
  import sys
  import pickle
  (buildername, tree, app, locale) = sys.argv[1:5]
  builder = pickle.load(open(buildername + '/builder'))
  builder.basedir = buildername
  builder.determineNextBuildNumber()
  print r.renderStats(builder, tree, app, locale)
