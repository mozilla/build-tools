#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os, sys
import time
import devicemanagerSUT as devicemanager

from sut_lib import clearFlag, setFlag, checkDeviceRoot, stopProcess, checkStalled, waitForDevice

# main() RETURN CODES
RETCODE_SUCCESS = 0
RETCODE_ERROR = 1
RETCODE_KILLSTALLED = 2

def main(tegra=None, dm=None):
    assert ((tegra is not None) or (dm is not None)) # Require one to be set

    tegra_name = os.environ['SUT_NAME']
    pidDir    = os.path.join('/builds/', tegra_name)
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
        clearFlag(flagFile, dump=True)

    if dm is None:
        print "Connecting to: " + tegra
        dm = devicemanager.DeviceManagerSUT(tegra)
        dm.debug = 5

    for p in processNames:
        if dm.dirExists('/data/data/%s' % p):
            print dm.uninstallAppAndReboot(p)
            waitForDevice(dm)
    
    # Now Verify that they are all gone
    for p in processNames:
        if dm.dirExists('/data/data/%s' % p):
            setFlag(errorFile, "Unable to properly uninstall %s" % p)
            return RETCODE_ERROR

    devRoot  = checkDeviceRoot(dm)

    if not str(devRoot).startswith("/mnt/sdcard"):
        setFlag(errorFile, "Remote Device Error: devRoot from devicemanager [%s] is not correct" % str(devRoot))
        return RETCODE_ERROR

    if dm.dirExists(devRoot):
        status = dm.removeDir(devRoot)
        print "removeDir() returned [%s]" % status
        if status is None or not status:
           setFlag(errorFile, "Remote Device Error: call to removeDir() returned [%s]" % status)
           return RETCODE_ERROR
        if dm.dirExists(devRoot):
            setFlag(errorFile, "Remote Device Error: Unable to properly remove %s" % devRoot)
            return RETCODE_ERROR

    if not dm.fileExists('/system/etc/hosts'):
        print "restoring /system/etc/hosts file"
        try:
            dm.sendCMD(['exec mount -o remount,rw -t yaffs2 /dev/block/mtdblock3 /system'])
            data = "127.0.0.1 localhost"
            dm.verifySendCMD(['push /mnt/sdcard/hosts ' + str(len(data)) + '\r\n', data], newline=False)
            dm.verifySendCMD(['exec dd if=/mnt/sdcard/hosts of=/system/etc/hosts'])
        except devicemanager.DMError, e:
            print "Exception hit while trying to restore /system/etc/hosts: %s" % str(e)
            setFlag(errorFile, "failed to restore /system/etc/hosts")
            return RETCODE_ERROR
        if not dm.fileExists('/system/etc/hosts'):
            setFlag(errorFile, "failed to restore /system/etc/hosts")
            return RETCODE_ERROR
        else:
            print "successfully restored hosts file, we can test!!!"

    errcode = checkStalled(tegra_name)
    if errcode > 1:
        if errcode == 2:
            print "processes from previous run were detected and cleaned up"
        elif errocode == 3:
            setFlag(errorFile, "Remote Device Error: process from previous test run present")
            return RETCODE_KILLSTALLED

    return RETCODE_SUCCESS

if __name__ == '__main__':
    if (len(sys.argv) <> 2):
        print "usage: cleanup.py <tegra name || ip address>"
        sys.exit(RETCODE_ERROR)

    retval = main(tegra=sys.argv[1])
    sys.exit(retval)
