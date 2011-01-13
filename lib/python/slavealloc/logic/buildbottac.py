import time
import socket

from slavealloc.data import model

tac_template = """\
# AUTOMATICALLY GENERATED - DO NOT MODIFY
# generated: %(gendate)s on %(genhost)s
from twisted.application import service
from buildbot.slave.bot import BuildSlave
from twisted.python.logfile import LogFile
from twisted.python.log import ILogObserver, FileLogObserver

maxdelay = 300
buildmaster_host = %(buildmaster_host)r
passwd = %(passwd)r
maxRotatedFiles = None
basedir = %(basedir)r
umask = 002
slavename = %(slavename)r
usepty = 1
rotateLength = 1000000
port = %(port)r
keepalive = None

application = service.Application('buildslave')
logfile = LogFile.fromFullPath("twistd.log", rotateLength=rotateLength,
                             maxRotatedFiles=maxRotatedFiles)
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)
s = BuildSlave(buildmaster_host, port, slavename, passwd, basedir,
               keepalive, usepty, umask=umask, maxdelay=maxdelay)
s.setServiceParent(application)
"""

def make_buildbot_tac(engine, slavename, allocation):
    info = dict()

    # we'll need info on the slave itself, e.g., basedir
    q = model.slaves.select(whereclause=(model.slaves.c.name == slavename))
    q.bind = engine
    slaverow = q.execute().fetchone()
    print slaverow

    info['gendate'] = time.ctime()
    info['genhost'] = socket.getfqdn()
    info['buildmaster_host'] = allocation.fqdn
    info['port'] = allocation.pb_port
    info['slavename'] = slavename
    info['basedir'] = slaverow.basedir
    info['passwd'] = 'TODO' # TODO!!

    return tac_template % info
