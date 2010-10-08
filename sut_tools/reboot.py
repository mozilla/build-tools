#!/usr/bin/env python

import sys
import time
import devicemanager

if (len(sys.argv) <> 2):
  print "usage: reboot.py <ip address>"
  sys.exit(1)

print "connecting to: " + sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])

dm.reboot(wait=False)
