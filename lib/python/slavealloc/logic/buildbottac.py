import time
import socket

template_header = """\
# AUTOMATICALLY GENERATED - DO NOT MODIFY
# generated: %(gendate)s on %(genhost)s

"""

tac_template_disabled = template_header + """\
print "SLAVE DISABLED; NOT STARTING"

import sys
sys.exit(0)
"""

default_template = """\
from twisted.application import service
from buildbot.slave.bot import BuildSlave

maxdelay = 300
buildmaster_host = %(buildmaster_host)r
passwd = %(passwd)r
maxRotatedFiles = None
basedir = %(basedir)r
umask = 002
slavename = %(slavename)r
usepty = False
rotateLength = 1000000
port = %(port)r
keepalive = None

application = service.Application('buildslave')
try:
    from twisted.python.logfile import LogFile
    from twisted.python.log import ILogObserver, FileLogObserver
    logfile = LogFile.fromFullPath("twistd.log", rotateLength=rotateLength,
                             maxRotatedFiles=maxRotatedFiles)
    application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
except ImportError:
    pass # old Twisted install - mostly on geriatric slaves
s = BuildSlave(buildmaster_host, port, slavename, passwd, basedir,
               keepalive, usepty, umask=umask, maxdelay=maxdelay)
s.setServiceParent(application)
"""

def make_buildbot_tac(allocation):
    info = dict()

    info['gendate'] = time.ctime()
    info['genhost'] = socket.getfqdn()

    # short-circuit for disabled slaves
    if not allocation.enabled:
        return tac_template_disabled % info

    info['buildmaster_host'] = allocation.master_fqdn
    info['port'] = allocation.master_pb_port
    info['slavename'] = allocation.slavename
    info['basedir'] = allocation.slave_basedir
    info['passwd'] = allocation.slave_password
    template = template_header + (allocation.template or default_template)

    return unicode(template % info).encode('utf8')
