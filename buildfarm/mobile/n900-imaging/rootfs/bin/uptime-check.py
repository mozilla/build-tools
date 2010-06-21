#!/usr/bin/env python

import os, sys, time

MAX_UPTIME = 10*60*60 # 10hours
OFFSET_FILE = '/builds/uptime-offset'
REBOOT_CMD = '/bin/reboot-user'
LOG_FILE = '/var/log/uptime.log'

def main():
    log = open(LOG_FILE, 'a+')
    print >>log, '%s - starting up' % time.asctime(time.localtime())
    log.flush()
    while True:
        up_f = open("/proc/uptime")
        up_s = up_f.readline()
        up_f.close()
        up_t = float(up_s.split(' ')[0])
        if os.path.exists(OFFSET_FILE):
            off_file = open(OFFSET_FILE)
            off_line = off_file.readline()
            off_file.close()
            off_time = float(off_line.split(' ')[0])
        else:
            off_time = 0
        if (up_t - off_time) > MAX_UPTIME:
            print >> log, '%s - i have been up too long -- rebooting' % \
                    time.asctime(time.localtime())
            log.flush()
            os.execv(REBOOT_CMD, [REBOOT_CMD])
            print >> log, 'Wow, i am really messed up!'
            log.flush()
        time.sleep(60)

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
