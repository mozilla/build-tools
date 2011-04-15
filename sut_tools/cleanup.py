#!/usr/bin/env python

import os, sys
import time
import devicemanager

from sut_lib import clearFlag, setFlag, checkDeviceRoot

if (len(sys.argv) <> 2):
    print "usage: cleanup.py <ip address>"
    sys.exit(1)

cwd       = os.getcwd()
flagFile  = os.path.join(cwd, '..', 'proxy.flg')
errorFile = os.path.join(cwd, '..', 'error.flg')

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
