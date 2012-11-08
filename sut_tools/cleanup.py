#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os, sys
from mozdevice import devicemanagerSUT as devicemanager
from sut_lib import clearFlag, setFlag, checkDeviceRoot, checkStalled, \
                    waitForDevice, log, soft_reboot

# main() RETURN CODES
RETCODE_SUCCESS = 0
RETCODE_ERROR = 1
RETCODE_KILLSTALLED = 2

def main(device=None, dm=None, doCheckStalled=True):
    assert ((device is not None) or (dm is not None)) # Require one to be set

    device_name = os.environ['SUT_NAME']
    pidDir    = os.path.join('/builds/', device_name)
    errorFile = os.path.join(pidDir, 'error.flg')

    processNames = [ 'org.mozilla.fennec',
                     'org.mozilla.fennec_aurora',
                     'org.mozilla.fennec_unofficial',
                     'org.mozilla.firefox',
                     'org.mozilla.firefox_beta',
                     'org.mozilla.roboexample.test',
                   ]

    if dm is None:
        log.info("Connecting to: " + device)
        dm = devicemanager.DeviceManagerSUT(device)
        dm.debug = 5

    packages = dm._runCmds([ { 'cmd': 'exec pm list packages' }])
    for package in packages.split('\n'):
        for proc in processNames:
            if package.strip() == "package:%s" % proc:
                try:
                    log.info(dm.uninstallAppAndReboot(proc))
                    waitForDevice(dm)
                except devicemanager.DMError, err:
                    setFlag(errorFile, "Remote Device Error: Unable to uninstall %s and reboot: %s" % (proc, err))
                    return RETCODE_ERROR

    # Now Verify that they are all gone
    packages = dm._runCmds([ { 'cmd': 'exec pm list packages' }])
    for package in packages.split('\n'):
        for proc in processNames:
            if package == "package:%s" % proc:
                setFlag(errorFile, "Remote Device Error: Unable to properly uninstall %s" % proc)
                return RETCODE_ERROR

    devRoot  = checkDeviceRoot(dm)

    if not str(devRoot).startswith("/mnt/sdcard"):
        setFlag(errorFile, "Remote Device Error: devRoot from devicemanager [%s] is not correct" % str(devRoot))
        return RETCODE_ERROR

    if dm.dirExists(devRoot):
        status = dm.removeDir(devRoot)
        log.info("removeDir() returned [%s]" % status)
        if status is None or not status:
            setFlag(errorFile, "Remote Device Error: call to removeDir() returned [%s]" % status)
            return RETCODE_ERROR
        if dm.dirExists(devRoot):
            setFlag(errorFile, "Remote Device Error: Unable to properly remove %s" % devRoot)
            return RETCODE_ERROR

    if not dm.fileExists('/system/etc/hosts'):
        log.info("restoring /system/etc/hosts file")
        try:
            dm._runCmds([{'cmd': 'exec mount -o remount,rw -t yaffs2 /dev/block/mtdblock3 /system'}])
            data = "127.0.0.1 localhost"
            dm._runCmds([{'cmd': 'push /mnt/sdcard/hosts ' + str(len(data)) + '\r\n', 'data': data}])
            dm._runCmds([{'cmd': 'exec dd if=/mnt/sdcard/hosts of=/system/etc/hosts'}])
        except devicemanager.DMError, e:
            setFlag(errorFile, "Remote Device Error: Exception hit while trying to restore /system/etc/hosts: %s" % str(e))
            return RETCODE_ERROR
        if not dm.fileExists('/system/etc/hosts'):
            setFlag(errorFile, "Remote Device Error: failed to restore /system/etc/hosts")
            return RETCODE_ERROR
        else:
            log.info("successfully restored hosts file, we can test!!!")

    if doCheckStalled:
        errcode = checkStalled(device_name)
        if errcode > 1:
            if errcode == 2:
                log.error("processes from previous run were detected and cleaned up")
            elif errocode == 3:
                setFlag(errorFile, "Remote Device Error: process from previous test run present")
                return RETCODE_KILLSTALLED

    return RETCODE_SUCCESS

if __name__ == '__main__':
    device_name = None
    if (len(sys.argv) <> 2):
        if os.getenv('SUT_NAME') in (None, ''):
            print "usage: cleanup.py [device name]"
            print "   Must have $SUT_NAME set in environ to omit device name"
            sys.exit(RETCODE_ERROR)
        else:
            device_name = os.getenv('SUT_NAME')
            log.info("INFO: Using device '%s' found in env variable" % device_name)
    else:
        device_name = sys.argv[1]

    retval = main(device=device_name)
    sys.stdout.flush()
    sys.exit(retval)
