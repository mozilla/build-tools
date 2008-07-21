from twisted.internet import defer, reactor
from buildbot.process.buildstep import BuildStep
from buildbot.steps.shell import ShellCommand, WithProperties
from buildbot.process.buildstep import LoggingBuildStep, LoggedRemoteCommand
from buildbot.status import builder

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
    self.command = ['cvs', '-q', '-z3', 'co', '-r', b]
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


class MakeCheckout(ShellCommand):
  haltOnFailure = 1
  
  debug = True
  
  def __init__(self, workdir, apps, **kwargs):
    """
    workdir is the workdir, apps is 
    - a hash mapping either the 'tree' or the 'buildername' to a list of apps
    - a list of app names.
    """
    self.apps = apps
    
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
    
    try:
      apps = self.apps[self.getProperty('tree')]
    except KeyError:
      apps = self.apps[self.getProperty('buildername')]
    except KeyError, e:
      if not isinstance(apps, list):
        raise e
      apps = self.apps
    
    if 'env' not in self.remote_kwargs:
      self.remote_kwargs['env'] = {}
    self.remote_kwargs['env']['MOZ_CO_PROJECT'] = ','.join(apps)
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
