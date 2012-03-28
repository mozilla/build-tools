#!/usr/bin/env python

import sys
import os
import time
from sut_lib import pingTegra, setFlag
import devicemanagerSUT as devicemanager
from updateSUT import target_version as EXPECTED_SUT_VERSION
from updateSUT import connect, version

MAX_RETRIES = 5
EXPECTED_TEGRA_SCREEN = 'X:1024 Y:768'
EXPECTED_TEGRA_SCREEN_ARGS = {'width': 1024, 'height': 768, 'type': 'crt'}

errorFile = None
dm = None

def dmAlive(dm):
    """ Check that a devicemanager connection is still active

    Returns False on failure, True on Success
    """
    try:
        # We want to be paranoid for the types of exceptions we might get
        if dm.getCurrentTime():
            return True
    except:
        pass # the actual exception holds no additional value here
    setFlag(errorFile, "Device manager lost connection to tegra")
    return False

def canPing(tegra):
    """ Check a tegra is reachable by ping

    Returns False on failure, True on Success
    """
    curRetry = 0
    print "INFO: attempting to ping tegra"
    while curRetry < MAX_RETRIES:
        ret, _ = pingTegra(tegra)
        if not ret:
            curRetry += 1
            if curRetry == MAX_RETRIES:
                setFlag(errorFile, "Unable to ping tegra after %s Retries" % MAX_RETRIES)
                print "WARNING: Unable to ping tegra after %s try" % MAX_RETRIES
                return False
            else:
                print "INFO: Unable to ping tegra after %s try. Sleeping for 90s then retrying" % curRetry
                time.sleep(90)
        else:
            break # we're done here
    return True

def canTelnet(tegra):
    """ Checks if we can establish a Telnet session (via devicemanager)

    Sets global `dm`
    Returns False on failure, True on Success
    """
    global dm
    curRetry = 0
    sleepDuration = 0
    while curRetry < MAX_RETRIES:
        try:
            dm = connect(tegra, sleepDuration)
        except:
            curRetry += 1
            if curRetry == MAX_RETRIES:
                setFlag(errorFile, "Unable to connect to tegra after %s Retries" % MAX_RETRIES)
                print "WARNING: Unable to connect to tegra after %s try" % MAX_RETRIES
                return False
            else:
                print "INFO: Unable to connect to tegra after %s try" % curRetry
                sleepDuration = 90
        else:
            break # We're done here
    return True

def checkVersion(dm):
    """ Verify SUTAgent Version

    Returns False on failure, True on Success
    """
    if not dmAlive(dm):
       return False

    ver = version(dm)
    if ver != "SUTAgentAndroid Version %s" % EXPECTED_SUT_VERSION:
        setFlag(errorFile, "Unexpected ver on tegra, got '%s' expected '%s'" % \
                (ver, "SUTAgentAndroid Version %s" % EXPECTED_SUT_VERSION))
        return False
    print "INFO: Got expected SUTAgent version '%s'" % EXPECTED_SUT_VERSION
    return True

def checkAndFixScreen(dm):
    """ Verify the screen is set as we expect

    If the screen is incorrectly set, this function attempts to fix it,
    which ends up requiring a reboot of the tegra.

    Returns False if screen is wrong, True if correct
    """
    if not dmAlive(dm):
       return False

    # Verify we have the expected screen resolution
    info = dm.getInfo("screen")
    if not info["screen"][0] == EXPECTED_TEGRA_SCREEN:
        setFlag(errorFile, "Unexpected Screen on tegra, got '%s' expected '%s'" % \
                            (info["screen"][0], EXPECTED_TEGRA_SCREEN))
        if not dm.adjustResolution(**EXPECTED_TEGRA_SCREEN_ARGS):
            setFlag(errorFile, "Command to update resolution returned failure")
        else:
            dm.reboot() # Reboot sooner than cp would trigger a hard Reset
        return False
    print "INFO: Got expected screen size '%s'" % EXPECTED_TEGRA_SCREEN
    return True

def checkSDCard(dm):
    """ Attempt to write a temp file to the SDCard

    We use this existing verify script as the source of the temp file

    Returns False on failure, True on Success
    """
    if not dmAlive(dm):
       return False

    try:
        if not dm.dirExists("/mnt/sdcard"):
            setFlag(errorFile, "Mount of sdcard does not seem to exist")
            return False
        if dm.fileExists("/mnt/sdcard/writetest"):
            print "INFO: /mnt/sdcard/writetest left over from previous run, cleaning"
            dm.removeFile("/mnt/sdcard/writetest")
        print "INFO: attempting to create file /mnt/sdcard/writetest"
        if not dm.pushFile("/builds/sut_tools/verify.py", "/mnt/sdcard/writetest"):
            setFlag(errorFile, "unable to write to sdcard")
            return False
        if not dm.fileExists("/mnt/sdcard/writetest"):
            setFlag(errorFile, "Written tempfile doesn't exist on inspection")
            return False
        if not dm.removeFile("/mnt/sdcard/writetest"):
            setFlag(errorFile, "Unable to cleanup from written tempfile")
            return False
    except Exception, e:
        setFlag(errorFile, "Unknown error while testing ability to write to" \
                           "sdcard, see following exception: %s" % e)
        return False
    return True

def main(tegra):
    # Returns False on failure, True on Success
    global dm, errorFile
    tegraPath = os.path.join('/builds', tegra)
    errorFile = os.path.join(tegraPath, 'error.flg')

    if not canPing(tegra):
        # TODO Reboot via PDU if ping fails
        return False

    if not canTelnet(tegra):
        return False

    if not checkVersion(dm):
        # TODO Move updateSUT from cp to here
        return False

    # Resolution Check disabled for now; Bug 737427
    if False and not checkAndFixScreen(dm):
        return False

    if not checkSDCard(dm):
        return False

    return True

if __name__ == '__main__':
    if (len(sys.argv) <> 2):
        print "usage: verify.py <tegra name>"
        sys.exit(1)
    
    if main(sys.argv[1]) == False:
        sys.exit(1) # Not ok to proceed with startup

    sys.exit(0)
