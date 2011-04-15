#!/usr/bin/env python

import os, sys
import time
import random
import socket
import datetime
import devicemanager

from sut_lib import getOurIP, calculatePort, clearFlag, setFlag, checkDeviceRoot, \
                    getDeviceTimestamp, setDeviceTimestamp, \
                    getResolution, waitForDevice


# Stop buffering!
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

if (len(sys.argv) <> 3):
  print "usage: installApp.py <ip address> <localfilename>"
  sys.exit(1)

cwd       = os.getcwd()
source    = sys.argv[2]
proxyFile = os.path.join(cwd, '..', 'proxy.flg')
errorFile = os.path.join(cwd, '..', 'error.flg')
proxyIP   = getOurIP()
proxyPort = calculatePort()

print "connecting to: %s" % sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])
# Moar data!
dm.debug = 3
devRoot  = checkDeviceRoot(dm)

if devRoot is None or devRoot == '/tests':
    setFlag(errorFile, "Remote Device Error: devRoot from devicemanager [%s] is not correct - exiting" % devRoot)
    sys.exit(1)

workdir  = os.path.dirname(source)
filename = os.path.basename(source)
target   = os.path.join(devRoot, filename)
inifile  = os.path.join(workdir, 'fennec', 'application.ini')

getDeviceTimestamp(dm)
setDeviceTimestamp(dm)
getDeviceTimestamp(dm)

print "Installing %s" % target
if dm.pushFile(source, target):
    try:
        setFlag(proxyFile)
        print proxyIP, proxyPort
        dm.getInfo('process')
        dm.getInfo('memory')
        dm.getInfo('uptime')

        width, height = getResolution(dm)
        #adjust resolution down to allow fennec to install without memory issues
        if (width >= 1050 or height >= 1050):
            dm.adjustResolution(1024, 768, 'crt')
            dm.reboot(proxyIP, proxyPort)
            waitForDevice(dm)

        status = dm.updateApp(target, processName='org.mozilla.fennec', ipAddr=proxyIP, port=proxyPort)
        if status is not None and status:
            print "updateApp() call returned %s" % status

            if dm.pushFile(inifile, '/data/data/org.mozilla.fennec/application.ini'):
                dm.getInfo('process')
                dm.getInfo('memory')
                dm.getInfo('uptime')
                pid = dm.processExist('org.mozilla.fennec')
                print 'org.mozilla.fennec PID', pid
                if pid is not None:
                    dm.killProcess('org.mozilla.fennec')
                dm.getInfo('process')
            else:
                clearFlag(proxyFile)
                setFlag(errorFile, "Remote Device Error: unable to push %s" % inifile)
                sys.exit(1)
        else:
            clearFlag(proxyFile)
            setFlag(errorFile, "Remote Device Error: updateApp() call failed - exiting")
            sys.exit(1)

    finally:
        clearFlag(proxyFile)
else:
    clearFlag(proxyFile)
    setFlag(errorFile, "Remote Device Error: unable to push %s" % target)
    sys.exit(1)

time.sleep(60)

