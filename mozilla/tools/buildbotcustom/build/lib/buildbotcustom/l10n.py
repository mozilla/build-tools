from buildbotcustom import log
from buildbot.scheduler import BaseUpstreamScheduler
from buildbot.sourcestamp import SourceStamp
from buildbot import buildset, process
from subprocess import *
from itertools import izip
import os
import os.path

"""
mozl10n holds helper classes to factor information about repositories (l10n
and mozilla), getting relevant information from mozilla/client.mk.
It also provides schedulers and build classes to dispatch changesets onto
l10n builds, trying to be somewhat clever on check-outs.
"""

class tree(object):
  """
  tree holds classmethods to retrieve l10n data about a particular branch
  by asking mozilla/client.mk.
  """
  
  @classmethod
  def ensureClientMk(self, branch):
    """
    Get client.mk for the specified branch locally.
    """
    rv = call(["cvs", "-z3",
               "-d:pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
               "co", "-r", branch, "mozilla/client.mk"])
    if rv < 0:
      print >>sys.stderr, "cvs co failed", -rv
    return

  @classmethod
  def l10nDirs(self, branch, apps):
    """
    For the given branch and applications, return the list of directories
    with localization files, per client.mk.
    """
    lapps = apps[:]
    self.ensureClientMk(branch)
    of  = os.popen('make -f mozilla/client.mk ' + \
                   ' '.join(['echo-variable-LOCALES_' + app for app in lapps]))
    rv = {}
    for val in of.readlines():
      rv[lapps.pop(0)] = val.strip().split()
    
    return rv

  @classmethod
  def allLocales(self, branch, apps):
    """
    For the given branch and applications, return a hash mapping application
    to locales, as given by mozilla/foo/locales/all-locales.
    """
    lapps = apps[:]
    alllocales = ['mozilla/%s/locales/all-locales' % app \
                  for app in lapps]
    rv = call(["cvs", "-z3",
               "-d:pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
               "co", "-r", branch] + alllocales)
    if rv < 0:
      print >>sys.stderr, "cvs co failed", -rv
      return []
    rv = {}
    for app, allpath in izip(lapps, alllocales):
      rv[app] = [loc.strip() for loc in open(allpath).readlines()]

    return rv


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
      self.repository = ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'
    def expandLists(self, locs, list):
      return [self.expand(l, m) for m in list for l in locs]
  mozilla = _repe('/cvsroot', 'mozilla', 'http://bonsai.mozilla.org/')
  l10n = _repe('/l10n', 'l10n', 'http://bonsai-l10n.mozilla.org/')
  l10n.expand = lambda loc, mod: 'l10n/%s/%s/'%(loc,mod)
  l10n.repository = ':pserver:anonymous@cvs-mirror.mozilla.org:/l10n'


def getInfoFor(workdir, branch, apps=None, locales=None):
  """
  getInfoFor gathers a pathmap (list of directory application tuples)
  and locales info for a given branch and either a list of apps or
  locales info. It's using the workdir to check out client.mk and, if
  needed, app/locales/all-locales.
  """
  if not apps:
    apps = locales.keys()
  try:
    if not os.path.isdir(workdir):
      os.mkdir(workdir)
    os.chdir(workdir)
    
    L10nDirs = tree.l10nDirs(branch, apps)
    if not locales:
      locales = tree.allLocales(branch, apps)
  finally:
    os.chdir('..')
  
  tmp = {}
  for app, dirs in L10nDirs.iteritems():
    for basedir in dirs:
      if basedir not in tmp:
        tmp[basedir] = []
      tmp[basedir].append(app)
        
  pathmap = [(basedir, appl) for basedir, appl in tmp.iteritems()]
  return (pathmap, locales)


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
  
  def __init__(self, pathmap, locales, builders,
               branch = None, tree = None):
    self.locales = locales
    self.paths = pathmap
    self.builders = builders
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
      required_apps = set()
      for basepath, apps in self.paths:
        if not path.startswith(basepath):
          continue
        apps = [app for app in apps if loc in self.locales[app]]
        if not apps:
          # this application / locale combination is not ours
          continue
        required_apps.update(apps)
      if not required_apps:
        continue
      try:
        to_add = required_apps - toBuild[loc]
        toBuild[loc].update(to_add)
      except KeyError:
        toBuild[loc] = required_apps
        to_add = required_apps
      if to_add:
        self.debug("adding %s for %s" % (', '.join(to_add), loc))
    for loc, apps in toBuild.iteritems():
      for app in apps:
        self.parent.queueBuild(app, loc, self.builders, change,
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
  
  def __init__(self, pathmap, locales, builders,
               branch = None, tree = None):
    self.locales = locales
    self.paths = pathmap
    self.builders = builders
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
    apps = set()
    for file in change.files:
      if not file.startswith("mozilla/"):
        self.debug("Ignoring change %d, not our rep" % change.number)
        return
      modEnd = file.find('/locales/en-US/')
      if modEnd < 0:
        continue
      basedir = file[len('mozilla/'):modEnd]
      for bd, newapps in self.paths:
        if bd != basedir:
          continue
        apps.update(newapps)
        break
    for app in apps:
      for loc in self.locales[app]:
        self.parent.queueBuild(app, loc, self.builders, change,
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
  
  def __init__(self, name, treeStableTimer = None):
    """
    @param name: the name of this Scheduler
    @param treeStableTimer: the duration, in seconds, for which the tree
                            must remain unchanged before a build will be
                            triggered. This is intended to avoid builds
                            of partially-committed fixes.
    """
    
    BaseUpstreamScheduler.__init__(self, name)
    self.treeStableTimer = treeStableTimer
    self.nextBuildTime = None
    self.timer = None

    self.dispatchers = []
    self.queue = []
    self.lastChange = {}
  
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
  def addDispatcher(self, dispatcher):
    """
    Add an IBaseDispatcher instance to this Scheduler.
    """
    self.dispatchers.append(dispatcher)
    dispatcher.setParent(self)

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
      self.submit(bs)
  
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
    changes = self.build_status.getChanges()
    log.debug("build",
              'do we really have no changes here yet? len is '+str(len(changes)))
    changes += bd.changes
    self.setProperty('app', bd.app)
    self.setProperty('locale', bd.locale)
    self.setProperty('needsCheckout', bd.needsCheckout)
    reason = bd.app + ' ' + bd.locale
    if bd.tree:
      self.setProperty('tree', bd.tree)
      reason = bd.tree + ': ' + reason

    process.base.Build.setupBuild(self, expectations)
    
    # overwrite the reason, we know better than base.Build
    self.build_status.setReason(reason)
