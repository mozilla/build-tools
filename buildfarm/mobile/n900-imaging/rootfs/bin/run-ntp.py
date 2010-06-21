#!/usr/bin/env python

import os, sys, time, subprocess

NTPCOMMAND = '/usr/bin/ntpdate'
NTPSERVER = 'ntp1.build.mozilla.org'
LOG_FILE = '/var/log/ntpdate.log'

def main():
    log = open(LOG_FILE, 'w+') #don't care for long logs
    print >>log, '\n%s - starting up' % time.asctime(time.localtime())
    log.flush()
    while True:
        rv = subprocess.call([NTPCOMMAND, NTPSERVER], stdout=log,
                             stderr=log)
        if rv is 0:
            sys.exit(0)
        time.sleep(5)

if __name__=="__main__":
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError, e:
        print >>sys.stderr, 'first fork failed %d %s' %(e.errno, e.strerror)
        sys.exit(1)

    os.chdir("/")
    os.setsid()
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
        else:
            main()
    except OSError, e:
        print >>sys.stderr, 'second fork failed %d %s' %(e.errno, e.strerror)
        sys.exit(1)
