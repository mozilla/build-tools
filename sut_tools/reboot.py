#!/usr/bin/env python


import os, sys
from mozdevice import devicemanagerSUT as devicemanager
import socket
import random
import time
from sut_lib import getOurIP, calculatePort, clearFlag, setFlag, waitForDevice, \
                    log, soft_reboot

def reboot(dm):
    cwd       = os.getcwd()
    deviceName = os.path.basename(cwd)
    errorFile = os.path.join(cwd, '..', 'error.flg')
    proxyIP   = getOurIP()
    proxyPort = calculatePort()

    try:
        dm.getInfo('process')
        log.info(dm._runCmds([{'cmd': 'exec su -c "logcat -d -v time *:W"'}]))

        log.info('forcing device reboot')
        status = soft_reboot(dm=dm, device=deviceName, ipAddr=proxyIP, port=proxyPort)
        log.info(status)
    finally:
        try:
            waitForDevice(dm, waitTime=300)
        except SystemExit:
            setFlag(errorFile, "Remote Device Error: call for device reboot failed")
            return 1

    sys.stdout.flush()
    return 0

if __name__ == '__main__':
    if (len(sys.argv) <> 2):
        print "usage: reboot.py <ip address>"
        sys.exit(1)

    deviceIP = sys.argv[1]
    print "connecting to: %s" % deviceIP
    dm = devicemanager.DeviceManagerSUT(deviceIP)
    dm.debug = 5
    sys.exit(reboot(dm))

