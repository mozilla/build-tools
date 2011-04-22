#!/usr/bin/env python

import os, sys
import devicemanager
import socket
import random
import time
from sut_lib import getOurIP, calculatePort, clearFlag, setFlag


if (len(sys.argv) <> 2):
  print "usage: reboot.py <ip address>"
  sys.exit(1)

cwd       = os.getcwd()
proxyFile = os.path.join(cwd, '..', 'proxy.flg')
proxyIP   = getOurIP()
proxyPort = calculatePort()

print "connecting to: %s" % sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])

setFlag(proxyFile)
try:
    status = dm.reboot(ipAddr=proxyIP, port=proxyPort)
    print status
finally:
    clearFlag(proxyFile)

#if status is None or not status:
#    print "Remote Device Error: call for device reboot failed"
#    sys.exit(1)
