from twisted.python import log as log2
from buildbotcustom import log
from buildbot.scheduler import BaseUpstreamScheduler
from buildbot.sourcestamp import SourceStamp
from buildbot import buildset, process
from buildbot.process import properties
from twisted.internet import protocol, utils, reactor, error, defer
from twisted.web.client import HTTPClientFactory, getPage
from itertools import izip
from ConfigParser import ConfigParser
from cStringIO import StringIO
import os
import os.path

from Mozilla import Paths


class AsyncLoader(Paths.L10nConfigParser):
  pendingLoads = 0
  def loadConfigs(self):
    self.d = defer.Deferred()
    self.pendingLoads += 1
    d = self._getPage(self.inipath)
    def _cbDone(contents):
      self.onLoadConfig(StringIO(contents))
      return defer.succeed(True)
    def _cbErr(rv):
      self.pendingLoads -= 1
      return self.d.errback(rv)
    d.addCallback(_cbDone)
    d.addCallbacks(self._loadDone, _cbErr)
    return self.d

  def onLoadConfig(self, f):
    log2.msg("onLoadConfig called")
    Paths.L10nConfigParser.onLoadConfig(self,f)

  def addChild(self, url):
    cp = self.__class__(url, **self.defaults)
    d = cp.loadConfigs()
    self.pendingLoads += 1
    d.addCallbacks(self._loadDone, self.d.errback)
    self.children.append(cp)

  def getAllLocales(self):
    return self._getPage(self.all_url)

  def _getPage(self, path):
    return getPage(path)

  def _loadDone(self, result):
    self.pendingLoads -= 1
    if not self.pendingLoads:
      self.d.callback(True)

class CVSProtocol(protocol.ProcessProtocol):

  def __init__(self, cmd):
    self.d = defer.Deferred()
    self.data = ''
    self.errdata = ''
    self.cmd = cmd

  def connectionMade(self):
    self.transport.closeStdin()

  def outReceived(self, data):
    self.data += data

  def errReceived(self, data):
    # chew away what cvs blurbs at us
    self.errdata += data
    pass

  def processEnded(self, reason):
    if isinstance(reason.value, error.ProcessDone):
      self.d.callback(self.data)
    else:
      reason.value.args = (self.errdata,)
      self.d.errback(reason)

class CVSAsyncLoader(AsyncLoader):
  CVSROOT = ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'
  BRANCH = None

  def __init__(self, inipath, **kwargs):
    AsyncLoader.__init__(self, inipath, **kwargs)
    self.inipath = inipath

  def _getPage(self, path):
    args = ['cvs', '-d', self.CVSROOT, 'co']
    if self.BRANCH is not None:
      args += ['-r', self.BRANCH]
    args += ['-p', path]
    pp = CVSProtocol(' '.join(args))
    reactor.spawnProcess(pp, 'cvs', args, {})
    return pp.d


class repositories(object):
  """
  Helper to store some information about the cvs repositories we use.
  
  It provides the cvsroot and the bonsai url. For l10n purposes, there
  are two functions, expand, and expandLists, which take the locale
  and the module, or lists for both, resp., and returns the list of
  directories, suitable both for cvs check out and bonsai.
  
  Predefined are the repositories mozilla and l10n.
  """
  class _repe:
    def __init__(self, root, base, bonsai):
      self.cvsroot = root
      self.base = base
      self.bonsai = bonsai
      self.expand = lambda loc, mod: 'mozilla/%s/locales/'%mod
      self.repository = 'l10nbld@cvs.mozilla.org:/cvsroot'
    def expandLists(self, locs, list):
      return [self.expand(l, m) for m in list for l in locs]
  mozilla = _repe('/cvsroot', 'mozilla', 'http://bonsai.mozilla.org/')
  l10n = _repe('/l10n', 'l10n', 'http://bonsai-l10n.mozilla.org/')
  l10n.expand = lambda loc, mod: 'l10n/%s/%s/'%(loc,mod)
  l10n.repository = 'l10nbld@cvs.mozilla.org:/l10n'


def configureDispatcher(config, section, scheduler):
  """
  """
  log2.msg('configureDispatcher for ' + section)
  buildtype = config.get(section, 'type')
  if buildtype not in ['cvs', 'hg']:
    raise RuntimeError('non-cvs l10n builds not supported yet')
  if buildtype == 'cvs':
    CVSAsyncLoader.CVSROOT = repositories.mozilla.repository
    cp = CVSAsyncLoader(config.get(section, 'l10n.ini'))
    cp.BRANCH = config.get(section, 'mozilla')
  else:
    l10n_ini_temp = '%(repo)s/%(mozilla)s/index.cgi/raw-file/tip/%(l10n.ini)s'
    cp = AsyncLoader(l10n_ini_temp % dict(config.items(section)))
  def _addDispatchers(dirs, locales, builders):
    if buildtype == 'cvs':
      scheduler.addDispatcher(L10nDispatcher(dirs, locales, builders,
                                             config.get(section, 'app'),
                                             config.get(section, 'l10n'),
                                             section),
                              section, locales)
      scheduler.addDispatcher(EnDispatcher(dirs, locales, builders,
                                           config.get(section, 'app'),
                                           config.get(section, 'mozilla'),
                                           section,
                                           prefix = 'mozilla/'))
      log2.msg('both dispatchers added for ' + section)
    else:
      scheduler.addDispatcher(HgL10nDispatcher(dirs, locales, builders,
                                               config.get(section, 'app'),
                                               config.get(section, 'l10n'),
                                               section),
                              section, locales)
      scheduler.addDispatcher(EnDispatcher(dirs, locales, builders,
                                           config.get(section, 'app'),
                                           config.get(section, 'mozilla'),
                                           section))
      log2.msg('both hg l10n dispatchers added for ' + section)
    buildermap = scheduler.parent.botmaster.builders
    for b in builders:
      try:
        buildermap[b].builder_status.addPointEvent([section, "set", "up"])
      except KeyError:
        log2.msg("Can't find builder %s for %s" % (b, section))
  def _cbLoadedLocales(locales, dirs, builders):
    log2.msg("loaded all locales")
    locales = locales.split()
    _addDispatchers(dirs, locales, builders)
  def _cbLoadedConfig(rv):
    log2.msg('config loaded for ' + section)
    dirs = dict(cp.directories()).keys()
    dirs.sort()
    builders = config.get(section, 'builders').split()
    locales = config.get(section, 'locales')
    if locales == 'all':
      d = cp.getAllLocales()
      d.addCallback(_cbLoadedLocales, dirs, builders)
      return
    _addDispatchers(dirs, locales.split(), builders)
    return
  def _errBack(msg):
    log2.msg("loading %s failed with %s" % (section, msg))
    buildermap = scheduler.parent.botmaster.builders
    for b in builders:
      buildermap[b].builder_status.addPointEvent([section, "setup", "failed"])
  d = cp.loadConfigs()
  d.addCallbacks(_cbLoadedConfig, _errBack)
  return d

"""
Dispatchers

The dispatchers know about which changes impact which localizations and 
applications. They're used in the Scheduler, and enable the scheduler to 
work on multiple branch combinations and multiple applications.
"""
class IBaseDispatcher(object):
  """
  Interface for dispatchers.
  """
  log = "dispatcher"
  
  def dispatch(self, change, sink):
    """
    Scheduler calls dispatch for each change, the dispatcher is expected
    to call sink.queueBuild for each build that is supposed to run.
    Scheduler will coalescent duplicate builders.
    """
    raise NotImplented

  def debug(self, msg):
    log.debug(self.log, msg)


class L10nDispatcher(IBaseDispatcher):
  """
  Dispatcher taking care about one branch in the l10n rep.
  It's using 
  - an array of module-app tuples and
  - a hash mapping apps to locales
  to figure out which apps-locale combos need to be built. It ignores
  changes that are not affecting its combos.
  It can pass around a tree name, too.
  """
  
  def __init__(self, paths, locales, builders, app, 
               branch = None, tree = None):
    self.locales = locales
    self.paths = paths
    self.builders = builders
    self.app = app
    self.branch = branch
    self.tree = tree
    self.parent = None
    self.log += '.l10n'
    if tree:
      self.log += '.' + tree

  def setParent(self, parent):
    self.parent = parent

  def listBuilderNames(self):
    return self.builders
  
  def dispatchChange(self, change):
    self.debug("adding change %d" % change.number)
    toBuild = {}
    if self.branch and self.branch != change.branch:
      self.debug("not our branch, ignore, %s != %s" %
                 (self.branch, change.branch))
      return
    for file in change.files:
      pathparts = file.split('/',2)
      if pathparts[0] != 'l10n':
        self.debug("non-l10n changeset ignored")
        return
      if len(pathparts) != 3:
        self.debug("l10n path doesn't contain locale and path")
        return
      loc, path = pathparts[1:]
      if loc not in self.locales:
        continue
      for basepath in self.paths:
        if not path.startswith(basepath):
          continue
        toBuild[loc] = True
      self.debug("adding %s for %s" % (self.app, loc))
    for loc in toBuild.iterkeys():
      self.parent.queueBuild(self.app, loc, self.builders, change,
                             tree = self.tree)

class HgL10nDispatcher(L10nDispatcher):
  def dispatchChange(self, change):   
    self.debug("adding change %d" % change.number)
    if self.branch and self.branch != change.branch:
      self.debug("not our branch, ignore, %s != %s" %
                 (self.branch, change.branch))
      return
    if not hasattr(change, 'locale'):
      log2.msg("I'm confused, the branches match, but this is not a locale change")
      return
    doBuild = False
    for file in change.files:
      for basepath in self.paths:
        if file.startswith(basepath):
          doBuild = True
          break
    if not doBuild:
      self.debug("dropping change %d, not our app" % change.number)
      return
    self.parent.queueBuild(self.app, change.locale, self.builders, change,
                           tree = self.tree)

class EnDispatcher(IBaseDispatcher):
  """
  Dispatcher watching one branch on the main mozilla repository.
  It's using 
  - an array of module-app tuples and
  - a hash mapping apps to locales
  to figure out which apps-locale combos need to be built. For each application
  affected by a change, it queues a build for all locales for that app.
  It can pass around a tree name, too.
  """
  
  def __init__(self, paths, locales, builders, app,
               branch , tree , prefix = ''):
    self.locales = locales
    self.paths = paths
    self.builders = builders
    self.app = app
    self.branch = branch
    self.tree = tree
    self.parent = None
    self.log += '.en'
    self.log += '.' + tree
    self.prefix = prefix

  def setParent(self, parent):
    self.parent = parent

  def listBuilderNames(self):
    return self.builders
  
  def dispatchChange(self, change):
    self.debug("adding change %d" % change.number)
    if self.branch and self.branch != change.branch:
      self.debug("not our branch, ignore, %s != %s" %
                 (self.branch, change.branch))
      return
    needsBuild = False
    for file in change.files:
      if not file.startswith(self.prefix):
        self.debug("Ignoring change %d, not our rep" % change.number)
        return
      file = file.replace(self.prefix, '', 1)
      modEnd = file.find('/locales/en-US/')
      if modEnd < 0:
        continue
      basedir = file[:modEnd]
      for bd in self.paths:
        if bd != basedir:
          continue
        needsBuild = True
        break
    if needsBuild:
      for loc in self.locales:
        self.parent.queueBuild(self.app, loc, self.builders, change,
                               tree = self.tree)


class Scheduler(BaseUpstreamScheduler):
  """
  Scheduler used for l10n builds.

  It's using several Dispatchers to create build items depending
  on the submitted changes.
  Scheduler is designed to be used with its special Build class,
  which actually pops the build items and moves the relevant information
  onto build properties for steps to use.
  """
  
  compare_attrs = ('name', 'treeStableTimer')
  
  def __init__(self, name, inipath, treeStableTimer = None):
    """
    @param name: the name of this Scheduler
    @param treeStableTimer: the duration, in seconds, for which the tree
                            must remain unchanged before a build will be
                            triggered. This is intended to avoid builds
                            of partially-committed fixes.
    """
    
    BaseUpstreamScheduler.__init__(self, name)
    self.inipath = inipath
    self.treeStableTimer = treeStableTimer
    self.nextBuildTime = None
    self.timer = None

    self.dispatchers = []
    self.queue = []
    self.lastChange = {}
    self.locales = {}

  def startService(self):
    log2.msg("starting l10n scheduler")
    cp = ConfigParser()
    cp.read(self.inipath)
    for tree in cp.sections():
      reactor.callWhenRunning(configureDispatcher,
                              cp, tree, self)

  class NoMergeStamp(SourceStamp):
    """
    We're going to submit a bunch of build requests for each change. That's
    how l10n goes. This source stamp impl keeps them from being merged by
    the build master.
    """
    def canBeMergedWith(self, other):
      return False

  # dispatching routines
  def addDispatcher(self, dispatcher, tree = None, locales = None):
    """
    Add an IBaseDispatcher instance to this Scheduler.
    """
    self.dispatchers.append(dispatcher)
    dispatcher.setParent(self)
    if tree is not None and locales is not None:
      self.locales[tree] = locales

  def queueBuild(self, app, locale, builders, change, tree = None):
    """
    Callback function for dispatchers to tell us what to build.
    This function actually submits the buildsets on non-mergable
    sourcestamps.
    """
    changes = [change]
    log.debug("scheduler", "queueBuild: build %s for change %d" % 
              (', '.join(builders), change.number))
    props = properties.Properties()
    props.updateFromProperties(self.properties)
    props.update(dict(app=app, locale=locale, tree=tree,
                      needsCheckout = True), 'Scheduler')
    bs = buildset.BuildSet(builders,
                           Scheduler.NoMergeStamp(changes=changes),
                           reason = "%s %s" % (tree, locale),
                           properties = props)
    self.submitBuildSet(bs)
  
  # Implement IScheduler
  def addChange(self, change):
    log.debug("scheduler",
              "addChange: Change %d, %s" % (change.number, change.asText()))
    for dispatcher in self.dispatchers:
      dispatcher.dispatchChange(change)

  def listBuilderNames(self):
    builders = set()
    for dispatcher in self.dispatchers:
      builders.update(dispatcher.listBuilderNames())
    return list(builders)

  def getPendingBuildTimes(self):
    if self.nextBuildTime is not None:
      return [self.nextBuildTime]
    return []


class Build(process.base.Build):
  """
  I subclass process.Build just to set some properties I get from
  the scheduler in setupBuild.
  """
  pass
