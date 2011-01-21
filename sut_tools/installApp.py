#!/usr/bin/env python

import os, sys
import time
import random
import socket
import devicemanager


def setFlag(contents=''):
    print flagFile
    h = open(flagFile, 'w+')
    h.write(contents)
    h.close()

def clearFlag():
    if os.path.exists(flagFile):
        os.remove(flagFile)

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

# Stop buffering!
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

if (len(sys.argv) <> 3):
  print "usage: installApp.py <ip address> <localfilename>"
  sys.exit(1)

cwd       = os.getcwd()
source    = sys.argv[2]
flagFile  = os.path.join(cwd, '..', 'proxy.flg')
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
    print "Remote Device Error: devRoot from devicemanager [%s] is not correct - exiting" % devRoot
    sys.exit(1)

workdir  = os.path.dirname(source)
filename = os.path.basename(source)
target   = os.path.join(devRoot, filename)
inifile  = os.path.join(workdir, 'fennec', 'application.ini')

print "Installing %s" % target
if dm.pushFile(source, target):
    try:
        setFlag()
        print proxyIP, proxyPort
        status = dm.updateApp(target, processName='org.mozilla.fennec', ipAddr=proxyIP, port=proxyPort)
        if status is not None:
            print "updateApp() call returned %s" % status
            dm2 = devicemanager.DeviceManager(sys.argv[1])
            dm2.debug = 3
            print "devroot %s" % dm2.getDeviceRoot()
            if not dm2.pushFile(inifile, '/data/data/org.mozilla.fennec/application.ini'):
                print "Remote Device Error: unable to push %s" % inifile
                clearFlag()
                sys.exit(1)
        else:
            print "Remote Device Error: updateApp() call failed - exiting"
            clearFlag()
            sys.exit(1)

    finally:
        clearFlag()

time.sleep(60)

