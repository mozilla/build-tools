#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os, sys
import devicemanagerSUT as devicemanager
import socket
import random
import time
import datetime
from sut_lib import getOurIP, calculatePort, clearFlag, setFlag, waitForDevice
from sut_lib import getLastLine

if (len(sys.argv) <> 2):
  print "usage: reboot.py <ip address>"
  sys.exit(1)

cwd       = os.getcwd()
proxyFile = os.path.join(cwd, '..', 'proxy.flg')
errorFile = os.path.join(cwd, '..', 'error.flg')
forceRebootFile = os.path.join(cwd, '..', 'forceReboot.flg')
proxyIP   = getOurIP()
proxyPort = calculatePort()

stringedNow = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
setFlag(forceRebootFile, stringedNow)

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
        setFlag(errorFile, "Remote Device Error: call for device reboot failed")
    clearFlag(proxyFile)

sys.stdout.flush()
time.sleep(20*60) # Let Buildbot Die or ForcedRebootFlag kill us

#if status is None or not status:
#    print "Remote Device Error: call for device reboot failed"
#    sys.exit(1)
