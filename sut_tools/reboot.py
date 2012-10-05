#!/usr/bin/env python


import os, sys
from mozdevice import devicemanagerSUT as devicemanager
import socket
import random
import time
from sut_lib import getOurIP, calculatePort, clearFlag, setFlag, waitForDevice, log

def reboot(dm):
    cwd       = os.getcwd()
    proxyFile = os.path.join(cwd, '..', 'proxy.flg')
    errorFile = os.path.join(cwd, '..', 'error.flg')
    proxyIP   = getOurIP()
    proxyPort = calculatePort()

    setFlag(proxyFile)
    try:
        dm.getInfo('process')
        log.info(dm._runCmds([{'cmd': 'exec su -c "logcat -d -v time *:W"'}]))

        log.info('calling dm.reboot()')
        status = dm.reboot(ipAddr=proxyIP, port=proxyPort)
        log.info(status)
    finally:
        try:
            waitForDevice(dm, waitTime=300)
        except SystemExit:
            clearFlag(proxyFile)
            setFlag(errorFile, "Remote Device Error: call for device reboot failed")
            return 1
        clearFlag(proxyFile)

    sys.stdout.flush()
    return 0

if __name__ == '__main__':
    if (len(sys.argv) <> 2):
        print "usage: reboot.py <ip address>"
        sys.exit(1)

    print "connecting to: %s" % sys.argv[1]
    dm = devicemanager.DeviceManagerSUT(sys.argv[1])
    dm.debug = 5
    sys.exit(reboot(dm))

