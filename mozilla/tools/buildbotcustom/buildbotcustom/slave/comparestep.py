from twisted.internet import reactor, defer
from twisted.python import log

from buildbot.slave.registry import registerSlaveCommand
from buildbot.slave.commands import Command
from buildbot.status.builder import SUCCESS

import os
from Mozilla.Paths import EnumerateApp
from Mozilla.CompareLocales import compareApp

class CompareCommand(Command):
  """
  Do CompareLocales on the slave.

  To be able to run this, you have to

    import Mozilla.slave

  when starting python on the slave via PYHTONSTARTUP
  """
  
  debug = True
  
  def setup(self, args):
    self.locale = args['locale']
    self.application = args['application']
    self.workdir = args['workdir']
    ## more

  def start(self):
    if self.debug:
      log.msg('Compare started')

    d = defer.Deferred()
    d.addCallback(self.doCompare)
    reactor.callLater(0, d.callback, None)
    d.addBoth(self.finished)
    return d

  def doCompare(self, *args):
    log.msg('Starting to compare %s in %s' % (self.locale, self.workdir))
    self.sendStatus({'header': 'Comparing %s against en-US for %s\n' \
                     % (self.locale, self.workdir)})
    cwd = os.getcwd()
    if self.debug:
      log.msg("I'm in  %s"%os.getcwd())
    workingdir = os.path.join(self.builder.basedir, self.workdir)
    if self.debug:
      log.msg('trying to import Mozilla from %s'%os.getcwd())
    app = EnumerateApp(workingdir)
    app.addApplication(self.application, [self.locale])
    o = compareApp(app)
    self.sendStatus({'result': o})
    pass

  def finished(self, *args):
    log.msg('finished called with args: %s'%args)
    self.sendStatus({'rc':0})

registerSlaveCommand('moz:comparelocales', CompareCommand, '0.1')
