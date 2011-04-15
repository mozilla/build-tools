#!/usr/bin/env python

import os, sys
import devicemanager
import socket
import random
import time
from sut_lib import getOurIP, calculatePort


if (len(sys.argv) <> 2):
  print "usage: reboot.py <ip address>"
  sys.exit(1)

proxyIP   = getOurIP()
proxyPort = calculatePort()

print "connecting to: %s" % sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])

status = dm.reboot(ipAddr=proxyIP, port=proxyPort)
print status

#if status is None or not status:
#    print "Remote Device Error: call for device reboot failed"
#    sys.exit(1)
