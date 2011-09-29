#!/usr/bin/env python


import os, sys
import devicemanagerSUT as devicemanager
import socket
import random
import time
from sut_lib import getOurIP, calculatePort, clearFlag, setFlag, waitForDevice

if (len(sys.argv) <> 2):
  print "usage: reboot.py <ip address>"
  sys.exit(1)

cwd       = os.getcwd()
proxyFile = os.path.join(cwd, '..', 'proxy.flg')
errorFile = os.path.join(cwd, '..', 'error.flg')
proxyIP   = getOurIP()
proxyPort = calculatePort()

print "connecting to: %s" % sys.argv[1]
dm = devicemanager.DeviceManagerSUT(sys.argv[1])
dm.debug = 5

setFlag(proxyFile)
try:
    dm.getInfo('process')
    print dm.sendCMD(['exec su -c "logcat -d -v time *:W"'])

    print 'calling dm.reboot()'

    status = dm.reboot(ipAddr=proxyIP, port=proxyPort)
    print status
finally:
    try:
        waitForDevice(dm, waitTime=600)
    except SystemExit:
        clearFlag(proxyFile)
        setFlag(errorFile, "Remote Device Error: call for device reboot failed")
        sys.exit(1)
        
    clearFlag(proxyFile)

#if status is None or not status:
#    print "Remote Device Error: call for device reboot failed"
#    sys.exit(1)
