#!/usr/bin/env python

import os, sys
import time
import devicemanager


def setFlag(flagFile, contents=None):
    print flagFile
    h = open(flagFile, 'a+')
    if contents is not None:
        print contents
        h.write(contents)
    h.close()
    time.sleep(30)

if (len(sys.argv) <> 2):
    print "usage: cleanup.py <ip address>"
    sys.exit(1)

flagFile  = os.path.join(os.getcwd(), '../proxy.flg')
errorFile = os.path.join(os.getcwd(), '../error.flg')

if os.path.exists(flagFile):
    print "Warning proxy.flg found during cleanup"
    os.remove(flagFile)

print "Connecting to: " + sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])

dm.debug = 5
devRoot = dm.getDeviceRoot()

if devRoot is None or devRoot == '/tests':
    setFlag(errorFile, "Remote Device Error: devRoot from devicemanager [%s] is not correct" % devRoot)
    sys.exit(1)

if dm.dirExists(devRoot):
    status = dm.removeDir(devRoot)
    print "removeDir() returned [%s]" % status
    if status is None or not status:
       setFlag(errorFile, "Remote Device Error: all to removeDir() failed")
       sys.exit(1)