#!/usr/bin/env python

import os, sys
import devicemanager
import socket
import random
import time


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

if (len(sys.argv) <> 2):
  print "usage: reboot.py <ip address>"
  sys.exit(1)

proxyIP   = getOurIP()
proxyPort = calculatePort()

print "connecting to: %s" % sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])

status = dm.reboot(ipAddr=proxyIP, port=proxyPort)
print status

#if status is None or not status:
#    print "Remote Device Error: call for device reboot failed"
#    sys.exit(1)
