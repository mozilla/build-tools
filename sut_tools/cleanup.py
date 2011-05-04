#!/usr/bin/env python

import os, sys
import time
import devicemanager

from sut_lib import clearFlag, setFlag, checkDeviceRoot, stopProcess

if (len(sys.argv) <> 2):
    print "usage: cleanup.py <ip address>"
    sys.exit(1)

cwd       = os.getcwd()
pidDir    = os.path.join(cwd, '..')
flagFile  = os.path.join(pidDir, 'proxy.flg')
errorFile = os.path.join(pidDir, 'error.flg')

if os.path.exists(flagFile):
    print "Warning proxy.flg found during cleanup"
    clearFlag(flagFile)

print "Connecting to: " + sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])

dm.debug = 5
devRoot  = checkDeviceRoot(dm)

if devRoot is None or devRoot == '/tests':
    setFlag(errorFile, "Remote Device Error: devRoot from devicemanager [%s] is not correct" % devRoot)
    sys.exit(1)

if dm.dirExists(devRoot):
    status = dm.removeDir(devRoot)
    print "removeDir() returned [%s]" % status
    if status is None or not status:
       setFlag(errorFile, "Remote Device Error: call to removeDir() returned [%s]" % status)
       sys.exit(1)

for f in ('runtestsremote', 'remotereftest', 'remotereftest.pid.xpcshell'):
    pidFile = os.path.join(pidDir, '%s.pid' % f)
    print "checking for previous test processes ... %s" % pidFile
    if os.path.exists(pidFile):
        print "pidfile from prior test run found, trying to kill"
        stopProcess(pidFile, f)
        if os.path.exists(pidFile):
            setFlag(errorFile, "Remote Device Error: process from previous test run present [%s]" % f)
            sys.exit(2)

