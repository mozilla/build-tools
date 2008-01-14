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
      self.rc = update.pop('rc')
      log.msg('Comparison of localizations completed')
    except KeyError:
      pass
    try:
      # get the Observer data from the slave
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
    summary = result['summary']
    self.completion = summary['completion']
    changed = summary['changed']
    unchanged = summary['unchanged']
    self.addHeader('%d translated, %d untranslated, %d%%\n'
                   % (changed, unchanged, self.completion))
    tbmsg = ''
    if 'tree' in self.args:
      tbmsg = self.args['tree'] + ': '
    tbmsg += "%(application)s %(locale)s" % self.args
    self.addStdout('TinderboxPrint:<a title="Build type">' + tbmsg + '</a>\n')
    self.addStdout('TinderboxPrint:<a title="Completion">%d%%</a>\n' %
                   self.completion)
    if self.rc == FAILURE:
      missing = sum([summary[k] \
                       for k in ['missing', 'missingInFiles'] \
                       if k in summary])
      self.addStdout('TinderboxPrint:<a title="Missing Strings">' + 
                     'M: %d' % missing + 
                     '</a>\n')
    self.addStdout(str(summary) + '\n')
    self.addStdout(pformat(result['details']) + '\n')
    self.step.setProperty('compare-result', result['details'])
    self.step.setProperty('coverage-result', summary)
    # It'd be nice if we didn't have to hardcode the URL to the comparison
    # Picking one that is relative to the waterfall
    self.step.addURL('comparison',
                     'compare/%s/%d' % \
                     (self.step.build.getProperty('buildername'),
                      self.step.build.getProperty('buildnumber')))
    # duh, really hardcoding for tinderbox.
    self.addStdout('TinderboxPrint:<a title="detailed comparison" ' +
                   'href="http://l10n.mozilla.org/buildbot/compare/%s/%d">' % \
                   (self.step.build.getProperty('buildername'),
                   self.step.build.getProperty('buildnumber')) +
                   'CL</a>\n')
  
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

  name = "moz_comparelocales"
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
           
