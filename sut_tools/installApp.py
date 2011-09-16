#!/usr/bin/env python

import os, sys
import time
import random
import socket
import datetime
import devicemanager

from sut_lib import getOurIP, calculatePort, clearFlag, setFlag, checkDeviceRoot, \
                    getDeviceTimestamp, setDeviceTimestamp, \
                    getResolution, waitForDevice, runCommand


# Stop buffering!
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

if (len(sys.argv) < 3):
  print "usage: installApp.py <ip address> <localfilename> [<processName>]"
  sys.exit(1)

cwd       = os.getcwd()
source    = sys.argv[2]
proxyFile = os.path.join(cwd, '..', 'proxy.flg')
errorFile = os.path.join(cwd, '..', 'error.flg')
proxyIP   = getOurIP()
proxyPort = calculatePort()

if len(sys.argv) > 3:
    processName = sys.argv[3]
else:
    processName = 'org.mozilla.fennec'

print "connecting to: %s" % sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])
# Moar data!
dm.debug = 3
devRoot  = checkDeviceRoot(dm)

if devRoot is None or devRoot == '/tests':
    setFlag(errorFile, "Remote Device Error: devRoot from devicemanager [%s] is not correct - exiting" % devRoot)
    sys.exit(1)

workdir      = os.path.dirname(source)
filename     = os.path.basename(source)
target       = os.path.join(devRoot, filename)
inifile      = os.path.join(workdir, 'fennec', 'application.ini')
remoteappini = os.path.join(workdir, 'talos', 'remoteapp.ini')

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
            print 'calling reboot'
            dm.reboot(proxyIP, proxyPort)
            waitForDevice(dm)

            width, height = getResolution(dm)
            if width != 1024 and height != 768:
                clearFlag(proxyFile)
                setFlag(errorFile, "Remote Device Error: Resolution change failed.  Should be %d/%d but is %d/%d" % (1024,768,width,height))
                sys.exit(1)

        print 'copying %s to %s' % (inifile, remoteappini)
        runCommand(['cp', inifile, remoteappini])

        status = dm.installApp(target)
        if status is None:
            print '-'*42
            print 'installApp() done - gathering debug info'
            dm.getInfo('process')
            dm.getInfo('memory')
            dm.getInfo('uptime')
            try:
                print dm.sendCMD(['exec su -c "logcat -d -v time *:W"'])
            except devicemanager.DMError, e:
                print "Exception hit while trying to run logcat: %s" % str(e)
                setFlag(errorFile, "Remote Device Error: can't run logcat")
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

