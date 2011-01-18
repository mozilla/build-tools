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

dm.removeDir(devRoot)
