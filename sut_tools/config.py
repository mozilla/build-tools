#!/usr/bin/env python

import os, sys
import time
import random
import socket
import devicemanagerSUT as devicemanager


def setFlag(flagfile, contents=None):
    print flagfile
    h = open(flagfile, 'a+')
    if contents is not None:
        print contents
        h.write('%s\n' % contents)
    h.close()
    time.sleep(30)

def clearFlag(flagfile):
    if os.path.exists(flagfile):
        os.remove(flagfile)

def calculatePort():
    s = os.environ['SUT_NAME']
    try:
        n = 50000 + int(s.split('-')[1])
    except:
        n = random.randint(40000, 50000)
    return n

def getOurIP():
    try:
        result = os.environ['CP_IP']
    except:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('mozilla.com', 80))
            result = s.getsockname()[0]
            s.close()
        except:
            result = None
            dumpException('unable to determine our IP address')

    return result

def getResolution(dm):
    parts = dm.getInfo('screen')['screen'][0].split()
    width = int(parts[0].split(':')[1])
    height = int(parts[1].split(':')[1])
    return width, height

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

# Stop buffering!
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

if (len(sys.argv) <> 3):
  print "usage: config.py <ip address> <testname>"
  sys.exit(1)

cwd       = os.getcwd()
testname  = sys.argv[2]
proxyFile = os.path.join(cwd, '..', 'proxy.flg')
errorFile = os.path.join(cwd, '..', 'error.flg')
proxyIP   = getOurIP()
proxyPort = calculatePort()
refWidth  = 1600 # x
refHeight = 1200 # y

print "connecting to: %s" % sys.argv[1]
dm = devicemanager.DeviceManagerSUT(sys.argv[1])
# Moar data!
dm.debug = 3
devRoot  = dm.getDeviceRoot()

# checking for /mnt/sdcard/...
print "devroot %s" % devRoot
if devRoot is None or devRoot == '/tests':
    setFlag(errorFile, "Remote Device Error: devRoot from devicemanager [%s] is not correct - exiting" % devRoot)
    sys.exit(1)

width, height = getResolution(dm)
print("current resolution X:%d Y:%d" % (width, height))

# adjust resolution up if we are part of a reftest run
if ('reftest' in testname or 'crashtest' in testname) and width < refWidth:
    try:
        setFlag(proxyFile)
        if dm.adjustResolution(width=refWidth, height=refHeight, type='crt'):
            status = dm.reboot(ipAddr=proxyIP, port=proxyPort)
            print status
            waitForDevice()

            width, height = getResolution(dm)
            print("current resolution X:%d Y:%d" % (width, height))
            if width != refWidth and height != refHeight:
                setFlag(errorFile, "Remote Device Error: current resolution X:%d Y:%d does not match what was set X:%d Y:%d" % (width, height, refWidth, refHeight))
                sys.exit(1)
    finally:
        clearFlag(proxyFile)

