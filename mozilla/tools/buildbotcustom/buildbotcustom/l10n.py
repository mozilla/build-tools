from twisted.python import log as log2
from buildbotcustom import log
from buildbot.scheduler import BaseUpstreamScheduler
from buildbot.sourcestamp import SourceStamp
from buildbot import buildset, process
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


def configureDispatcher(config, section, scheduler, builders):
  """
  """
  log2.msg('configureDispatcher for ' + section)
  if config.get(section, 'type', 'cvs') != 'cvs':
    raise RuntimeError('non-cvs l10n builds not supported yet')
  CVSAsyncLoader.CVSROOT = repositories.mozilla.repository
  cp = CVSAsyncLoader(config.get(section, 'l10n.ini'))
  cp.BRANCH = config.get(section, 'mozilla', None)
  def _addDispatchers(dirs, locales):
    scheduler.addDispatcher(L10nDispatcher(dirs, locales, builders,
                                           config.get(section, 'app'),
                                           config.get(section, 'l10n'),
                                           section))
    scheduler.addDispatcher(EnDispatcher(dirs, locales, builders,
                                         config.get(section, 'app'),
                                         config.get(section, 'mozilla'),
                                         section))
    log2.msg('both dispatchers added for ' + section)
    buildermap = scheduler.parent.botmaster.builders
    for b in builders:
      buildermap[b].builder_status.addPointEvent([section, "set", "up"])
  def _cbLoadedLocales(locales, dirs):
    log2.msg("loaded all locales")
    locales = locales.split()
    _addDispatchers(dirs, locales)
  def _cbLoadedConfig(rv):
    log2.msg('config loaded for ' + section)
    dirs = dict(cp.directories()).keys()
    dirs.sort()
    locales = config.get(section, 'locales', 'all')
    if locales == 'all':
      d = cp.getAllLocales()
      d.addCallback(_cbLoadedLocales, dirs)
      return
    _addDispatchers(dirs, locales)
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
               branch = None, tree = None):
    self.locales = locales
    self.paths = paths
    self.builders = builders
    self.app = app
    self.branch = branch
    self.tree = tree
    self.parent = None
    self.log += '.en'
    if tree:
      self.log += '.' + tree

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
      if not file.startswith("mozilla/"):
        self.debug("Ignoring change %d, not our rep" % change.number)
        return
      modEnd = file.find('/locales/en-US/')
      if modEnd < 0:
        continue
      basedir = file[len('mozilla/'):modEnd]
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
    self.locales = []

  def startService(self):
    log2.msg("starting l10n scheduler")
    cp = ConfigParser()
    cp.read(self.inipath)
    for tree in cp.sections():
      reactor.callWhenRunning(configureDispatcher,
                              cp, tree, self, ['linux-langpack'])

  class NoMergeStamp(SourceStamp):
    """
    We're going to submit a bunch of build requests for each change. That's
    how l10n goes. This source stamp impl keeps them from being merged by
    the build master.
    """
    def canBeMergedWith(self, other):
      return False

  class BuildDesc(object):
    """
    Helper object. We could actually use a dictionary, too, but this
    scopes the information clearly and makes up for nicer code via
    build.app instead of build['app'] etc.
    """
    def __init__(self, app, locale, builder, changes, tree = None):
      self.app = app
      self.locale = locale
      self.builder = builder
      self.changes = changes
      self.tree = tree
      self.needsCheckout = True
    
    def __eq__(self, other):
      return self.app == other.app and \
          self.locale == other.locale and \
          self.builder == other.builder and \
          self.tree == other.tree
    
    def __repr__(self):
      return "Build: %s %s %s" % (self.tree, self.app, self.locale)

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
    # create our own copy of the builder list to modify
    builders = list(builders)
    for build in self.queue:
      if app == build.app and \
         locale == build.locale and \
         build.builder in builders:
        log.debug("scheduler", "queueBuild found build for %s, %s on %s" %
                  (build.app, build.locale, build.builder))
        build.changes.append(change)
        builders.remove(build.builder)
        self.queue.remove(build)
        self.queue.insert(0, build)
        if not builders:
          log.debug("scheduler", "no new build needed for change %d" % change.number)
          return

    for builder in builders:
      log.debug("scheduler",
                "adding change %d to %s"  % (change.number, builder))
      self.queue.insert(0, Scheduler.BuildDesc(app, locale, builder, changes,
                                               tree))
      bs = buildset.BuildSet([builder],
                             Scheduler.NoMergeStamp(changes=changes))
      self.submitBuildSet(bs)
  
  def popBuildDesc(self, buildername, slavename):
    """
    Pop pending build details from the list for the given builder.
    Depending on the changes and the slave, it will request a checkout,
    or even a clobber (clobber not implemented).
    """
    if not self.queue:
      # no more builds pending
      log.debug("scheduler",
                "no more builds for %s, slave %s" % (buildername,slavename))
      return

    # get the latest build
    build = self.queue.pop()
    lastChange = build.changes[-1].number
    log.debug("scheduler", "popping 'til change %d, builder %s, slave %s" %
              (lastChange, buildername, slavename))
    log.debug("scheduler",
              "lastChange: %d, hash: %s" % (lastChange, str(self.lastChange)))
    log.debug("scheduler", "Building %s" % str(build))
    try:
      build.needsCheckout =  self.lastChange[(slavename, buildername)] < \
                            lastChange
    except KeyError:
      build.needsCheckout = True

    # it'd be cool if we could do this on successful check-out, but let's
    # be ignorant for now and assume that succeeds
    self.lastChange[(slavename, buildername)] = lastChange
    
    return build

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
  
  # this is the scheduler, needs to be set on the class in master.cfg
  buildQueue = None

  def setupBuild(self, expectations):
    bd = self.buildQueue.popBuildDesc(self.builder.name, self.slavename)
    if not bd:
      raise Exception("No build found for %s on %s, bad mojo" % \
                      (self.builder.name, self.slavename))
    process.base.Build.setupBuild(self, expectations)
    self.build_status.changes = tuple(bd.changes)
    self.setProperty('app', bd.app, 'setup')
    self.setProperty('locale', bd.locale, 'setup')
    self.setProperty('needsCheckout', bd.needsCheckout, 'setup')
    reason = bd.app + ' ' + bd.locale
    if bd.tree:
      self.setProperty('tree', bd.tree, 'setup')
      reason = bd.tree + ': ' + reason
    
    # overwrite the reason, we know better than base.Build
    self.build_status.setReason(reason)
