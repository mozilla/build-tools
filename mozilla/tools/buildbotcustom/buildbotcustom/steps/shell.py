from twisted.internet import defer, reactor
from buildbot.process.buildstep import BuildStep
from buildbot.steps.shell import ShellCommand, WithProperties
from buildbot.steps.source import Mercurial
from buildbot.process.buildstep import LoggingBuildStep, LoggedRemoteCommand
from buildbot.status import builder
from buildbotcustom.l10n import repositories

from twisted.python import log


class CVSCO(ShellCommand):
  haltOnFailure = 1
  
  debug = True
  
  def __init__(self, workdir, cvsroot, cvsmodule, branch = 'HEAD',
               date = None, **kwargs):
    """
    Create an CVSCO command.
    workdir is the workdir, cvsroot is the cvsroot, cvsmodule can be
    - a string, that's just checked out
    - a list (of strings), just checked out
    - a hash, CVSCO will try to find the value for 'tree' or 'buildername'
    and check that out.
    branch and date are the obvious again.
    """
    self.description = ["checking out"]
    self.descriptionDone = ["check out"]
    self.cvsroot = cvsroot
    self.branch = branch
    self.date = date
    if type(cvsmodule) == str:
      cvsmodule = [cvsmodule]
    self.targets = cvsmodule
    self.command = None # filled in on start()
    mykwargs = kwargs
    if 'env' not in mykwargs:
      mykwargs['env'] = {}
    mykwargs['env']['CVSROOT'] = self.cvsroot
    mykwargs['env']['CVS_RSH'] = 'ssh'
    ShellCommand.__init__(self, workdir, **mykwargs)

  def start(self):
    """
    Overwrite start to get the file list into our command.
    """
    doCheckout = self.build.getProperty('needsCheckout')
    if not doCheckout:
      if self.debug:
        log.msg("skipping CVSCO")
      return builder.SKIPPED
    
    files = self.build.allFiles()
    # Log the changed files to twistd.log
    if self.debug:
      log.msg("Build Files: %s" % files)
    b = self.branch
    if isinstance(b, dict):
      try:
        b = b[self.getProperty('tree')]
      except KeyError:
        b = b[self.getProperty('buildername')]
    self.command = ['cvs', '-q', '-z3', 'co']
    if b is not None:
      self.command += ['-r', b]
    if self.date:
      self.command += ['-D', self.date]
    targets = self.targets
    if isinstance(targets, dict):
      try:
        targets = targets[self.getProperty('tree')]
      except KeyError:
        targets = targets[self.getProperty('buildername')]
    self.command.extend(targets)
    
    return ShellCommand.start(self)


class NonLocaleMercurial(Mercurial):
    """Subclass of Mercurial pull step for the main tree of a l10n build."""

    def __init__(self, repourl, mainBranch, **kwargs):
        Mercurial.__init__(self, repourl=repourl, **kwargs)
        self.mainBranch = mainBranch
        self.addFactoryArguments(mainBranch=mainBranch)

    def startVC(self, branch, revision, patch):
        # strip out the "branch" which is fake... we always use a repourl
        self.repourl = self.build.getProperties().render(self.repourl)
        self.args = self.build.getProperties().render(self.args)
        Mercurial.startVC(self, None, revision, patch)

    def computeSourceRevision(self, changes):
        """Walk backwards through the list of changes: find the revision of
        the last change associated with our 'branch'."""

        if not changes:
            return None

        for change in changes[::-1]:
            if change.branch == self.mainBranch:
                return change.revision

        return None


class LocaleMercurial(Mercurial):
    """Subclass of Mercurial pull step for localized pulls."""

    haltOnFailure = True

    def __init__(self, locale, repourl, localesBranch, baseURL=None, **kwargs):
        if baseURL is not None:
            raise ValueError("baseURL must not be used with MercurialLocale")
        Mercurial.__init__(self, repourl=repourl, **kwargs)
        self.locale = locale
        self.localesBranch = localesBranch
        self.addFactoryArguments(locale=locale,
                                 localesBranch=localesBranch)

    def startVC(self, branch, revision, patch):
        # if we're running a main tree and locales in the same tree,
        # we get a "branch" parameter here which doesn't have the locale
        # information which is encoded in repoURL. Strip it.
        self.repourl = self.build.getProperties().render(self.repourl)
        self.locale = self.build.getProperties().render(self.locale)
        self.args = self.build.getProperties().render(self.args)
        log.msg("starting LocaleMercurial with repo %s and locale %s" % \
                (self.repourl, self.locale))
        Mercurial.startVC(self, None, revision, patch)

    def computeSourceRevision(self, changes):
        """Walk backwards through the list of changes: find the revision of
        the last change associated with this locale."""

        if not changes:
            return None

        for change in changes[::-1]:
            if change.branch == self.localesBranch and change.locale == self.locale:
                return change.revision

        return None

    def describe(self, done=False):
      # better be safe than sorry, not sure when startVC is called
      self.locale = self.build.getProperties().render(self.locale)
      return [done and "updated" or "updating", self.locale]

    def commandComplete(self, cmd):
        self.step_status.locale = self.locale
        Mercurial.commandComplete(self, cmd)


class MakeCheckout(ShellCommand):
  haltOnFailure = 1
  
  debug = True
  
  def __init__(self, workdir, **kwargs):
    """
    workdir is the workdir
    """
    
    ShellCommand.__init__(self, workdir, **kwargs)

  def start(self):
    """
    Overwrite start to get the file list into our command.
    """
    doCheckout = self.build.getProperty('needsCheckout')
    if not doCheckout:
      if self.debug:
        log.msg("skipping MakeCheckout")
      return builder.SKIPPED
    
    app = self.getProperty('app')
    locale = self.getProperty('locale')
    
    if 'env' not in self.remote_kwargs:
      self.remote_kwargs['env'] = {}
    self.remote_kwargs['env']['MOZ_CO_PROJECT'] = app
    self.remote_kwargs['env']['MOZ_CO_LOCALES'] = locale
    self.remote_kwargs['env']['LOCALES_CVSROOT'] = repositories.l10n.repository
    self.remote_kwargs['env']['CVS_RSH'] = 'ssh'
    
    return ShellCommand.start(self)


class Configure(ShellCommand):
  
  name = "configure"
  haltOnFailure = 1
  description = ["configuring"]
  descriptionDone = ["configure"]

  def __init__(self, app, srcdir, args, **kwargs):
    """
    app can be a WithProperties, as can be srcdir and workdir.
    args is a list of arguments to be passed to configure.
    """
    self.app = app
    self.srcdir = srcdir
    self.configure_args = args
    ShellCommand.__init__(self, **kwargs)

  def start(self):
    srcdir = self.srcdir
    if isinstance(srcdir, WithProperties):
      srcdir = self.build.getProperties().render(srcdir)
    app = self.app
    if isinstance(app, WithProperties):
      app = self.build.getProperties().render(app)
    self.command = [srcdir + '/configure'] + self.configure_args
    self.command.append('--enable-application=%s' % app)

    return ShellCommand.start(self)


class Upload(ShellCommand):
  """
  Simple scp command, which copies all files in the workdir to the 
  destination, and then removes them. It also adds a URL to the status,
  which is specified separately.
  """
  name = "upload"

  description = ["uploading"]
  descriptionDone = ["upload"]

  def __init__(self, scp_dest, http_dest, **kwargs):
    self.scp_dest = scp_dest
    self.http_dest = http_dest
    ShellCommand.__init__(self, **kwargs)

  def start(self):
    href = self.http_dest
    if isinstance(href, WithProperties):
      href = self.build.getProperties().render(href)
    dest = self.scp_dest
    if isinstance(dest, WithProperties):
      dest = self.build.getProperties().render(dest)
    self.addURL("D", href)
    self.command = "mkdir -p " + dest + "&&chmod 755 " + dest + "&& chmod 644 * && scp -p * " + dest + "&& rm *"

    return ShellCommand.start(self)
