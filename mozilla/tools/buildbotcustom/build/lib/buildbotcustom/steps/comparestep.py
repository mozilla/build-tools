import warnings

from twisted.python import log
from buildbot.process.buildstep import LoggingBuildStep, LoggedRemoteCommand
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, Results
from buildbot.steps.shell import WithProperties

from pprint import pformat

class ResultRemoteCommand(LoggedRemoteCommand):
  """
  Helper command class, extracts compare locale results from updates.
  """
  
  def remoteUpdate(self, update):
    log.msg("remoteUpdate called")
    result = None
    try:
      rc = update.pop('rc')
      log.msg('Comparison of localizations completed')
    except KeyError:
      pass
    try:
      result = update.pop('result')
    except KeyError:
      pass
    if len(update):
      # there's more than just us
      LoggedRemoteCommand.remoteUpdate(self, update)
      pass

    if not result:
      return

    rmsg = {}
    ## only one language, strip that from the result
    self.rc = SUCCESS
    for k, v in result.iteritems():
      if k.startswith('obsolete') or k.startswith('missing'):
        if not v or not len(v):
          continue
        rmsg[k] = v
        if k.startswith('missing'):
          # flag this as error
          self.rc = FAILURE
        elif self.rc == SUCCESS:
          self.rc = WARNINGS
    changed = result['changed']
    unchanged = result['unchanged']
    self.addHeader(Results[self.rc]+'\n')
    self.addHeader('%d translated, %d untranslated, %d%%\n'
                   % (changed, unchanged,
                      100*changed/(unchanged+changed)))
    self.completion = int(100*changed/(unchanged+changed))
    tbmsg = ''
    if 'tree' in self.args:
      tbmsg = self.args['tree'] + ': '
    tbmsg += "%(application)s %(locale)s" % self.args
    self.addStdout('TinderboxPrint:<a title="Build type">' + tbmsg + '</a>\n')
    self.addStdout('TinderboxPrint:<a title="Completion">%d/%d (%d%%)</a>\n' %
                    (changed, unchanged, self.completion))
    if self.rc == FAILURE:
      counts = [0, 0]
      if 'missing' in result:
        counts[0] = sum([sum([len(vv) for vv in v.values()]) \
                         for v in result['missing'].values()])
      if 'missingFiles' in result:
        counts[1] = sum([len(v.keys()) for v in result['missingFiles'].values()])
      self.addStdout('TinderboxPrint:<a title="Missing Strings/Files">' + 
                     '%d/%d' % tuple(counts) + 
                     '</a>\n')
    self.addStdout(pformat(rmsg))
    self.step.setProperty('compare-result', rmsg)
    self.step.setProperty('coverage-result', dict(changed=changed,
                                                  unchanged=unchanged))
  
  def remoteComplete(self, maybeFailure):
    log.msg('end with compare, rc: %s, maybeFailure: %s'%(self.rc, maybeFailure))
    if self.rc != FAILURE:
      maybeFailure = None
    LoggedRemoteCommand.remoteComplete(self, maybeFailure)
    return maybeFailure

class CompareLocale(LoggingBuildStep):
  """
  This class hooks up CompareLocales in the build master.
  """

  name = "moz:comparelocales"
  haltOnFailure = 1

  description = ["comparing"]
  descriptionDone = ["compare", "locales"]

  def __init__(self, workdir, locale, application, **kwargs):
    """
    @type  workdir: string
    @param workdir: local directory (relative to the Builder's root)
                    where the mozilla and the l10n trees reside

    @type  locale: string
    @param locale: Language code of the localization to be compared.

    @type  application: string
    @param application: Module name of the application to be compared,
                        for example, browser, or mail.
    """

    LoggingBuildStep.__init__(self, **kwargs)

    self.args = {'workdir'    : workdir,
                 'locale'     : locale,
                 'application': application}

  def describe(self, done=False):
    if done:
      return self.descriptionDone
    return self.description

  def start(self):
    log.msg('starting with compare')
    args = {}
    args.update(self.args)
    for k, v in args.iteritems():
      if isinstance(v, WithProperties):
                args[k] = v.render(self.build)
    try:
      args['tree'] = self.build.getProperty('tree')
    except KeyError:
      pass
    self.descriptionDone = [args['locale'], args['application']]
    cmd = ResultRemoteCommand(self.name, args)
    self.startCommand(cmd, [])
  
  def evaluateCommand(self, cmd):
    """Decide whether the command was SUCCESS, WARNINGS, or FAILURE.
    Override this to, say, declare WARNINGS if there is any stderr
    activity, or to say that rc!=0 is not actually an error."""

    return cmd.rc

  def getText(self, cmd, results):
    assert cmd.rc == results, "This should really be our own result"
    log.msg("called getText")
    txt = "no completion found for result %s" % results
    if hasattr(cmd, 'completion'):
      log.msg("rate is %d, results is %s" % (cmd.completion,results))
      text = ['%d%% translated' % cmd.completion]
    if False and cmd.missing > 0:
      text += ['missing: %d' % cmd.missing]
    return LoggingBuildStep.getText(self,cmd,results) + text
           
