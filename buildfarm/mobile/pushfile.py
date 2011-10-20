import os, sys
import time
import devicemanagerSUT as devicemanager

# Stop buffering!
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

if (len(sys.argv) <> 4):
  print "usage: pushfile.py <ip address> <localfilename> <targetfile>"
  sys.exit(1)

cwd = os.getcwd()

print "connecting to: %s" % sys.argv[1]
dm = devicemanager.DeviceManagerSUT(sys.argv[1])
dm.debug = 3

dm.pushFile(sys.argv[2], sys.argv[3])

