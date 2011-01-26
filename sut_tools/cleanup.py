#!/usr/bin/env python

import os, sys
import time
import devicemanager


def setFlag(flagFile, contents=''):
    print flagFile
    h = open(flagFile, 'w+')
    h.write(contents)
    h.close()

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
    print "Remote Device Error: devRoot from devicemanager [%s] is not correct" % devRoot
    setFlag(errorFile)
    time.sleep(30)
    sys.exit(1)

status = dm.removeDir(devRoot)

print "removeDir() returned [%s]" % status
#if status is None:
#    print "Remote Device Error: all to removeDir() failed"
#    setFlag(errorFile)
#    time.sleep(30)
#    sys.exit(1)