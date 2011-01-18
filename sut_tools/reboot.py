#!/usr/bin/env python

import os, sys
import devicemanager
import random


def calculatePort():
    s = os.environ['SUT_NAME']
    try:
        n = 50000 + int(s.split('-')[1])
    except:
        n = random.randint(40000, 50000)
    return n


if (len(sys.argv) <> 2):
  print "usage: reboot.py <ip address>"
  sys.exit(1)

proxyIP   = os.environ['CP_IP']
proxyPort = calculatePort()

print "connecting to: %s" % sys.argv[1]
dm = devicemanager.DeviceManager(sys.argv[1])

dm.reboot(ipAddr=proxyIP, port=proxyPort)

