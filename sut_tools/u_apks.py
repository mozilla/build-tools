#!/usr/bin/env python

import os, sys
import time
import socket
import random
import devicemanager


def calculatePort():
    if 'SUT_NAME' in os.environ:
        s = os.environ['SUT_NAME']
        try:
            n = 42000 + int(s.split('-')[1])
        except:
            n = random.randint(42000, 42999)
    else:
        n = random.randint(42000, 42999)

    return n

def getOurIP():
    try:
        result = os.environ['CP_IP']
    except:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.250.48.9', 80))
            result = s.getsockname()[0]
            s.close()
        except:
            result = None
            print 'unable to determine our IP address'

    return result

def checkDeviceRoot():
    dr = dm.getDeviceRoot()
    # checking for /mnt/sdcard/...
    print "devroot %s" % str(dr)
    if not dr or dr == '/tests':
        return None
    return dr

def waitForDevice(waitTime=60):
    print "Waiting for tegra to come back..."
    time.sleep(waitTime)
    tegraIsBack = False
    tries = 0
    maxTries = 20
    while tries <= maxTries:
        tries += 1
        print "Try %d" % tries
        if checkDeviceRoot() is not None:
            tegraIsBack = True
            break
        time.sleep(60)
    if not tegraIsBack:
        print("Remote Device Error: waiting for tegra timed out.")
        sys.exit(1)


if (len(sys.argv) <> 3):
    print "usage: u_apks.py <localdir> <tegra ip>"
    sys.exit(1)

cwd       = os.getcwd()
sourceDir = os.path.abspath(sys.argv[1])
tegraIP   = sys.argv[2]
proxyIP   = getOurIP()
proxyPort = calculatePort()
filelist  = []

for sourceFile in os.listdir(sourceDir):
    s = sourceFile.lower()

    if 'sutagentandroid' in s:
        print 'adding %s to queue' % sourceFile
        filelist.append((os.path.join(sourceDir, sourceFile), 'SUTAgentAndroid.apk', 'com.mozilla.SUTAgentAndroid'))
    elif 'watcher' in s:
        print 'adding %s to queue' % sourceFile
        filelist.append((os.path.join(sourceDir, sourceFile), 'Watcher.apk', 'com.mozilla.watcher'))
    else:
        print 'skipping %s' % sourceFile

if len(filelist) > 0:
    print "%s: connecting" % tegraIP
    dm = devicemanager.DeviceManager(tegraIP)
    # Moar data!
    dm.debug = 3
    devRoot  = checkDeviceRoot()

    # checking for /mnt/sdcard/...
    if devRoot is None:
        print "%s: devRoot from devicemanager [%s] is not correct - exiting" % (tegraIP, devRoot)
        sys.exit(1)

    for source, apk, process in filelist:
        target = os.path.join(devRoot, apk)

        print "%s: Installing %s to %s" % (tegraIP, source, target)
        if dm.pushFile(source, target):

            if 'watcher' in process:
                print "%s: calling uninstall for %s" % (tegraIP, target)
                status = dm.uninstallAppAndReboot(process)
                if status is not None and status:
                    print "%s: uninstallAppAndReboot() call returned %s" % (tegraIP, status)

                waitForDevice()

                print "%s: calling install for %s" % (tegraIP, target)
                status = dm.installApp(target)
                if status is not None and status:
                    print "%s: installApp() call returned %s" % (tegraIP, status)
            else:
                print "%s: calling update for %s %s" % (tegraIP, target, process)
                status = dm.updateApp(target, processName=process) #, ipAddr=proxyIP, port=proxyPort)
                if status is not None and status:
                    print "%s: updateApp() call returned %s" % (tegraIP, status)

            waitForDevice()

            if checkDeviceRoot is None:
                print "%s: devRoot from devicemanager is not correct.  updateApp() call not verified" % tegraIP
                sys.exit(1)

