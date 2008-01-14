from twisted.internet import reactor, defer
from twisted.python import log
from twisted.python.failure import Failure

from buildbot.slave.registry import registerSlaveCommand
from buildbot.slave.commands import Command
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION

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
    try:
      o = compareApp(app)
    except Exception, e:
      log.msg('%s comparison failed with %s' % (self.locale, str(e)))
      log.msg(Failure().getTraceback())
      self.rc = EXCEPTION
      return
    self.rc = SUCCESS
    summary = o.summary[self.locale]
    if 'obsolete' in summary and summary['obsolete'] > 0:
      self.rc = WARNINGS
    if 'missing' in summary and summary['missing'] > 0:
      self.rc = FAILURE
    if 'missingInFiles' in summary and summary['missingInFiles'] > 0:
      self.rc = FAILURE
    if 'errors' in summary and summary['errors'] > 0:
      self.rc = FAILURE
    total = sum(summary[k] for k in ['changed','unchanged','missing',
                                     'missingInFiles'])
    summary['completion'] = int((summary['changed'] * 100) / total)
    summary['total'] = total

    self.sendStatus({'result': dict(summary=dict(summary),
                                    details=o.details.toJSON())})
    pass

  def finished(self, *args):
    # sometimes self.rc isn't set here, no idea why
    try:
      rc = self.rc
    except AttributeError:
      rc = FAILURE
    self.sendStatus({'rc': rc})

registerSlaveCommand('moz_comparelocales', CompareCommand, '0.1')
