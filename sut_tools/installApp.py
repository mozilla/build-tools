#!/usr/bin/env python

import os, sys
import time
import random
import socket
import devicemanager


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
devRoot  = dm.getDeviceRoot()

# checking for /mnt/sdcard/...
print "devroot %s" % devRoot
if devRoot is None or devRoot == '/tests':
    setFlag(errorFile, "Remote Device Error: devRoot from devicemanager [%s] is not correct - exiting" % devRoot)
    sys.exit(1)

workdir  = os.path.dirname(source)
filename = os.path.basename(source)
target   = os.path.join(devRoot, filename)
inifile  = os.path.join(workdir, 'fennec', 'application.ini')

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
            waitForDevice()

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

