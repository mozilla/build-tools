#!/usr/bin/env python

import os, sys
import devicemanager

if (len(sys.argv) <> 3):
  print "usage: installApp.py <ip address> <localfilename>"
  sys.exit(1)

print "connecting to: " + sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])

devRoot  = dm.getDeviceRoot()
source   = sys.argv[2]
workdir  = os.path.dirname(source)
filename = os.path.basename(source)
target   = os.path.join(devRoot, filename)
inifile  = os.path.join(workdir, 'fennec', 'application.ini')

dm.pushFile(inifile, '/data/data/org.mozilla.fennec/application.ini')
dm.pushFile(source, target)
dm.installApp(target)
