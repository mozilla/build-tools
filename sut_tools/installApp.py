#!/usr/bin/env python

import os, sys
import time
import random
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


# Stop buffering!
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

if (len(sys.argv) <> 3):
  print "usage: installApp.py <ip address> <localfilename>"
  sys.exit(1)

cwd       = os.getcwd()
source    = sys.argv[2]
flagFile  = os.path.join(cwd, '..', 'proxy.flg')
proxyIP   = os.environ['CP_IP']
proxyPort = calculatePort()

print "connecting to: %s" % sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])
# Moar data!
dm.debug = 3
devRoot  = dm.getDeviceRoot()

# checking for /mnt/sdcard/...
print "devroot %s" % devRoot
if devRoot == '/tests':
    print "returned devRoot from devicemanager [%s] is not correct - exiting" % devRoot
    sys.exit(1)

workdir  = os.path.dirname(source)
filename = os.path.basename(source)
target   = os.path.join(devRoot, filename)
inifile  = os.path.join(workdir, 'fennec', 'application.ini')

print "Installing %s" % target
dm.pushFile(source, target)

try:
    setFlag()
    print proxyIP, proxyPort
    if dm.updateApp(target, processName='org.mozilla.fennec', ipAddr=proxyIP, port=proxyPort):
        dm2 = devicemanager.DeviceManager(sys.argv[1])
        dm2.debug = 3
        print "devroot %s" % dm2.getDeviceRoot()
        dm2.pushFile(inifile, '/data/data/org.mozilla.fennec/application.ini')
    else:
        print "updateApp() call failed - exiting"
        clearFlag()
        sys.exit(1)

finally:
    clearFlag()

time.sleep(60)

