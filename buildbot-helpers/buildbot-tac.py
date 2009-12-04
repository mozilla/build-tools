#!/usr/bin/python

import re

DEFAULT_HEADER = """\
from twisted.application import service
from buildbot.slave.bot import BuildSlave

"""
DEFAULT_FOOTER = """
application = service.Application('buildslave')
try:
  from twisted.python.logfile import LogFile
  from twisted.python.log import ILogObserver, FileLogObserver
  logfile = LogFile.fromFullPath("twistd.log", rotateLength=rotateLength,
                                 maxRotatedFiles=maxRotatedFiles)
  application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
except ImportError:
  # probably not yet twisted 8.2.0 and beyond, can't set log yet
  pass
s = BuildSlave(buildmaster_host, port, slavename, passwd, basedir,
               keepalive, usepty, umask=umask, maxdelay=maxdelay)
s.setServiceParent(application)
"""
BUILD_BUILDMASTER = "staging-master.build.mozilla.org"
TRY_BUILDMASTER   = "sm-staging-try-master.mozilla.org"
TALOS_BUILDMASTER = "talos-master.mozilla.org"

def quote_option(str, raw=False):
    str = re.sub("'", "\\'", str)
    if raw:
        return "r'%s'" % str
    else:
        return "'%s'" % str

def get_default_options(slavename):
    d = {'slavename': quote_option(slavename)}
    basedir = None
    buildmaster_host = None
    if 'moz2' in slavename or 'xserve' in slavename or 'try-' in slavename or \
      slavename.startswith('win32'):
        if 'try-' in slavename:
            buildmaster_host = TRY_BUILDMASTER
            d['port'] = 9982
        else:
            buildmaster_host = BUILD_BUILDMASTER
        if 'linux' in slavename or 'darwin9' in slavename or \
          'xserve' in slavename or 'mac' in slavename:
            basedir = '/builds/slave'
        elif 'win32' in slavename:
            basedir = 'e:\\builds\\moz2_slave'
    elif 'talos' in slavename or '-try' in slavename:
        buildmaster_host = TALOS_BUILDMASTER
        if '-try' in slavename:
            d['port'] = 9011
        if 'linux' in slavename or 'ubuntu' in slavename:
            basedir = '/home/mozqa/talos-slave'
        elif 'tiger' in slavename or 'leopard' in slavename:
            basedir = '/Users/mozqa/talos-slave'
        elif 'xp' in slavename or 'vista' in slavename:
            basedir = 'C:\\talos-slave'
    # quote_option will throw if defaults couldn't be found for either of these
    # These are processed separately because they should be unset if a default
    # wasn't found.
    try:
        d['buildmaster_host'] = quote_option(buildmaster_host)
    except TypeError:
        # Don't error out, because missing values may have been passed to
        # the program
        pass
    try:
        d['basedir'] = quote_option(basedir, raw=True)
    except TypeError:
        pass

    return d


class MissingOptionsError(Exception):
    pass

class BuildbotTac:
    defaults = {
      'port': 9010,
      'keepalive': None,
      'usepty': 1,
      # XX: probably shouldn't be stored as a string, but it makes things easier
      'umask': '002',
      'maxdelay': 300,
      'rotateLength': 1000000,
      'maxRotatedFiles': None
    }
    requiredOptions = ('basedir', 'buildmaster_host', 'slavename', 'passwd')

    def __init__(self, tacOptions, header=DEFAULT_HEADER, footer=DEFAULT_FOOTER,
                 filename="buildbot.tac"):
        self.tacOptions = self.defaults.copy()
        self.tacOptions.update(tacOptions)
        self.header = header
        self.footer = footer
        self.filename = filename

    def save(self):
        # Look for necessary, but missing options
        missingOptions = []
        for o in self.requiredOptions:
            if o not in self.tacOptions:
                missingOptions.append(o)
        if missingOptions:
            raise MissingOptionsError("Missing %s, cannot save %s" % \
              (missingOptions, self.filename))
        # If there wasn't any, save the file
        f = open(self.filename, "w")
        f.write(self.header)
        for key,value in self.tacOptions.iteritems():
            f.write("%s = %s\n" % (key, value))
        f.write(self.footer)



if __name__ == '__main__':
    from optparse import OptionParser
    import socket

    parser = OptionParser()
    parser.add_option("-f", "--filename", action="store", dest="filename",
                      default="buildbot.tac")
    parser.add_option("-d", "--basedir", action="store", dest="basedir")
    parser.add_option("-b", "--buildmaster", action="store", dest="buildmaster")
    parser.add_option("-n", "--slavename", action="store", dest="slavename")
    parser.add_option("-p", "--password", action="store", dest="password")

    (options, args) = parser.parse_args()

    slavename = options.slavename or socket.gethostname().split('.')[0]
    tacOptions = get_default_options(slavename)
    tacOptions['passwd'] = quote_option(options.password)
    if options.basedir:
        tacOptions['basedir'] = quote_option(options.basedir, raw=True)
    if options.buildmaster:
        tacOptions['buildmaster'] = quote_option(options.buildmaster)

    tac = BuildbotTac(tacOptions, filename=options.filename)
    tac.save()
