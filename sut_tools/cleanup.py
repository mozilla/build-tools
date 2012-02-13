#!/usr/bin/env python

import os, sys
import time
import devicemanagerSUT as devicemanager

from sut_lib import clearFlag, setFlag, checkDeviceRoot, stopProcess, checkStalled, waitForDevice

if (len(sys.argv) <> 2):
    print "usage: cleanup.py <ip address>"
    sys.exit(1)

cwd       = os.getcwd()
pidDir    = os.path.join(cwd, '..')
flagFile  = os.path.join(pidDir, 'proxy.flg')
errorFile = os.path.join(pidDir, 'error.flg')

processNames = [ 'org.mozilla.fennec',
                 'org.mozilla.fennec_aurora',
                 'org.mozilla.fennec_unofficial',
                 'org.mozilla.firefox',
                 'org.mozilla.firefox_beta',
                 'org.mozilla.roboexample.test', 
               ]

if os.path.exists(flagFile):
    print "Warning proxy.flg found during cleanup"
    clearFlag(flagFile)

print "Connecting to: " + sys.argv[1]
dm = devicemanager.DeviceManagerSUT(sys.argv[1])

dm.debug = 5
devRoot  = checkDeviceRoot(dm)

if not str(devRoot).startswith("/mnt/sdcard"):
    setFlag(errorFile, "Remote Device Error: devRoot from devicemanager [%s] is not correct" % str(devRoot))
    sys.exit(1)

if dm.dirExists(devRoot):
    status = dm.removeDir(devRoot)
    print "removeDir() returned [%s]" % status
    if status is None or not status:
       setFlag(errorFile, "Remote Device Error: call to removeDir() returned [%s]" % status)
       sys.exit(1)

if dm.fileExists('/system/etc/hosts'):
    print "removing /system/etc/hosts file"
    try:
        dm.sendCMD(['exec mount -o remount,rw -t yaffs2 /dev/block/mtdblock3 /system'])
        dm.sendCMD(['exec rm /system/etc/hosts'])
    except devicemanager.DMError, e:
        print "Exception hit while trying to remove /system/etc/hosts: %s" % str(e)
        setFlag(errorFile, "failed to remove /system/etc/hosts")
        sys.exit(1)
    if dm.fileExists('/system/etc/hosts'):
        setFlag(errorFile, "failed to remove /system/etc/hosts")
        sys.exit(1)
    else:
        print "successfully removed hosts file, we can test!!!"

errcode = checkStalled(os.environ['SUT_NAME'])
if errcode > 1:
    if errcode == 2:
        print "processes from previous run were detected and cleaned up"
    elif errocode == 3:
        setFlag(errorFile, "Remote Device Error: process from previous test run present")
        sys.exit(2)

for p in processNames:
    if dm.dirExists('/data/data/%s' % p):
        print dm.uninstallAppAndReboot(p)
        waitForDevice(dm)
