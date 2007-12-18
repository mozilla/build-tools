from twisted.internet import reactor, defer
from twisted.python import log

from buildbot.slave.registry import registerSlaveCommand
from buildbot.slave.commands import Command
from buildbot.status.builder import SUCCESS

import os

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
    try:
      wd = os.path.join(self.builder.basedir, self.workdir)
      os.chdir(wd)
      if self.debug:
        log.msg('trying to import Mozilla from %s'%os.getcwd())
      from Mozilla import CompareLocales
      rv = CompareLocales.compare(testLocales =
                                  {self.application: [self.locale]})
      ## compress results a bit
      ## XXX should be part of CompareLocales, really
      rv = rv[self.locale]
      for k, lst in rv.iteritems():
        if not k.startswith('missing') and not k.startswith('obsolete'):
          continue
        nv = {}
        for v in lst:
          if v[0] not in nv:
            nv[v[0]] = {}
          if v[1] not in nv[v[0]]:
            nv[v[0]][v[1]] = []
          if len(v) > 2:
            nv[v[0]][v[1]].append(v[2])
            ## this could be prettier, but lets just sort() each time
            nv[v[0]][v[1]].sort()
        rv[k] = nv
      self.sendStatus({'result':rv})
      pass
    finally:
      os.chdir(cwd)

  def finished(self, *args):
    log.msg('finished called with args: %s'%args)
    self.sendStatus({'rc':0})

registerSlaveCommand('moz:comparelocales', CompareCommand, '0.1')
