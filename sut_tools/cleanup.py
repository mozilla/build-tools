#!/usr/bin/env python

import os, sys
import devicemanager

if (len(sys.argv) <> 2):
    print "usage: cleanup.py <ip address>"
    sys.exit(1)

flagfile = os.path.join(os.getcwd(), '../proxy.flg')

if os.path.exists(flagfile):
    print "Warning proxy.flg found during cleanup"
    os.remove(flagfile)

print "Connecting to: " + sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])

dm.debug = 5
devRoot = dm.getDeviceRoot()

if devRoot is None or devRoot == '/tests':
    print "Remote Device Error: devRoot from devicemanager [%s] is not correct" % devRoot
    sys.exit(1)

status = dm.removeDir(devRoot)

print "removeDir() returned [%s]" % status
if status is None:
    print "Remote Device Error: all to removeDir() failed"
    sys.exit(1)