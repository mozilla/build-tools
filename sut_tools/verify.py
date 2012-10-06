#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import os
import time
from sut_lib import pingTegra, setFlag, connect, log
from mozdevice import devicemanagerSUT as devicemanager
import updateSUT

MAX_RETRIES = 5
EXPECTED_TEGRA_SCREEN = 'X:1024 Y:768'
EXPECTED_TEGRA_SCREEN_ARGS = {'width': 1024, 'height': 768, 'type': 'crt'}

errorFile = None
dm = None

watcherINI = "\r\n[watcher]\r\nPingTarget = bm-remote.build.mozilla.org\r\nstrikes = 0\r\n"

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
    setFlag(errorFile, "Automation Error: Device manager lost connection to tegra")
    return False

def canPing(tegra):
    """ Check a tegra is reachable by ping

    Returns False on failure, True on Success
    """
    curRetry = 0
    log.info("INFO: attempting to ping tegra")
    while curRetry < MAX_RETRIES:
        ret, _ = pingTegra(tegra)
        if not ret:
            curRetry += 1
            if curRetry == MAX_RETRIES:
                setFlag(errorFile, "Automation Error: Unable to ping tegra after %s attempts" % MAX_RETRIES)
                return False
            else:
                log.info("INFO: Unable to ping tegra after %s try. Sleeping for 90s then retrying" % curRetry)
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
                setFlag(errorFile, "Automation Error: Unable to connect to tegra after %s attempts" % MAX_RETRIES)
                return False
            else:
                log.info("INFO: Unable to connect to tegra after %s try" % curRetry)
                sleepDuration = 90
        else:
            break # We're done here
    return True

def checkVersion(dm, flag=False):
    """ Verify SUTAgent Version

    Returns False on failure, True on Success
    """
    if not dmAlive(dm):
       return False

    ver = updateSUT.version(dm)
    if not updateSUT.isVersionCorrect(ver=ver):
        if flag:
            setFlag(errorFile, "Remote Device Error: Unexpected ver on tegra, got '%s' expected '%s'" % \
                    (ver, "SUTAgentAndroid Version %s" % updateSUT.target_version))
        return False
    log.info("INFO: Got expected SUTAgent version '%s'" % updateSUT.target_version)
    return True

def updateSUTVersion(dm):
    """ Update SUTAgent Version

    Returns False on failure, True on Success
    """
    if not dmAlive(dm):
       return False

    retcode = updateSUT.doUpdate(dm)
    if retcode == updateSUT.RETCODE_SUCCESS:
        return True
    elif retcode == updateSUT.RETCODE_APK_DL_FAILED:
        setFlag(errorFile, "Remote Device Error: UpdateSUT: Unable to download " \
                  "new APK for SUTAgent")
    elif retcode == updateSUT.RETCODE_REVERIFY_FAILED:
        setFlag(errorFile, "Remote Device Error: UpdateSUT: Unable to re-verify " \
                  "that the SUTAgent was updated")
    elif retcode == updateSUT.RETCODE_REVERIFY_WRONG:
        # We will benefit from the SUT Ver being displayed on our dashboard
        if checkVersion(dm, flag=True):
            # we NOW verified correct SUT Ver, Huh?
            setFlag(errorFile, " Unexpected State: UpdateSUT found incorrect SUTAgent Version after "\
                      "updating, but we seem to be correct now.")
    # If we get here we failed to update properly
    return False

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
        setFlag(errorFile, "Remote Device Error: Unexpected Screen on tegra, got '%s' expected '%s'" % \
                            (info["screen"][0], EXPECTED_TEGRA_SCREEN))
        if not dm.adjustResolution(**EXPECTED_TEGRA_SCREEN_ARGS):
            setFlag(errorFile, "Command to update resolution returned failure")
        else:
            dm.reboot() # Reboot sooner than cp would trigger a hard Reset
        return False
    log.info("INFO: Got expected screen size '%s'" % EXPECTED_TEGRA_SCREEN)
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
            setFlag(errorFile, "Remote Device Error: Mount of sdcard does not seem to exist")
            return False
        if dm.fileExists("/mnt/sdcard/writetest"):
            log.info("INFO: /mnt/sdcard/writetest left over from previous run, cleaning")
            dm.removeFile("/mnt/sdcard/writetest")
        log.info("INFO: attempting to create file /mnt/sdcard/writetest")
        if not dm.pushFile(os.path.join(os.path.abspath(os.path.dirname( __file__ )), "verify.py"), "/mnt/sdcard/writetest"):
            setFlag(errorFile, "Remote Device Error: unable to write to sdcard")
            return False
        if not dm.fileExists("/mnt/sdcard/writetest"):
            setFlag(errorFile, "Remote Device Error: Written tempfile doesn't exist on inspection")
            return False
        if not dm.removeFile("/mnt/sdcard/writetest"):
            setFlag(errorFile, "Remote Device Error: Unable to cleanup from written tempfile")
            return False
    except Exception, e:
        setFlag(errorFile, "Remote Device Error: Unknown error while testing ability to write to " \
                           "sdcard, see following exception: %s" % e)
        return False
    return True

def cleanupTegra(dm, doCheckStalled):
    """ Do cleanup actions necessary to ensure starting in a good state

    Returns False on failure, True on Success
    """
    if not dmAlive(dm):
       return False

    import cleanup
    try:
        retval = cleanup.main(dm=dm, doCheckStalled=doCheckStalled)
        if retval == cleanup.RETCODE_SUCCESS:
            # All is good
            return True
    except:
        pass
    # Some sort of error happened above
    return False

def setWatcherINI(dm):
    """ If necessary Installs the (correct) watcher.ini for our infra

    Returns False on failure, True on Success
    """
    import hashlib
    realLoc = "/data/data/com.mozilla.watcher/files/watcher.ini"
    currentHash = hashlib.md5(watcherINI).hexdigest()

    def watcherDataCurrent():
        remoteFileHash = dm.getRemoteHash(realLoc)
        if currentHash != remoteFileHash:
            return False
        else:
            return True

    if not dmAlive(dm):
       return False
    
    try:
       if watcherDataCurrent():
           return True
    except:
        setFlag(errorFile, "Unable to identify if watcher.ini is current")
        return False

    try:
        tmpname = '/mnt/sdcard/watcher.ini'
        # Need to install it
        dm._runCmds([{'cmd': 'push %s %s\r\n' % (tmpname, len(watcherINI)), 'data': watcherINI}])
        dm._runCmds([{'cmd': 'exec su -c "dd if=%s of=%s"' % (tmpname, realLoc)}])
    except devicemanager.AgentError, err:
        log.info("Error while pushing watcher.ini: %s" % err)
        setFlag(errorFile, "Unable to properly upload the watcher.ini")
        return False
    
    try:
       if watcherDataCurrent():
           return True
    except:
        pass
    setFlag(errorFile, "Unable to verify the updated watcher.ini")
    return False


def verifyDevice(tegra, checksut=False, doCheckStalled=True, watcherINI=False):
    # Returns False on failure, True on Success
    global dm, errorFile
    tegraPath = os.path.join('/builds', tegra)
    errorFile = os.path.join(tegraPath, 'error.flg')

    if not canPing(tegra):
        # TODO Reboot via PDU if ping fails
        log.info("verifyDevice: failing to ping")
        return False

    if not canTelnet(tegra):
        log.info("verifyDevice: failing to telnet")
        return False

    if checksut and not checkVersion(dm):
        if not updateSUTVersion(dm):
            log.info("verifyDevice: failing to updateSUT")
            return False

    # Resolution Check disabled for now; Bug 737427
    if False and not checkAndFixScreen(dm):
        log.info("verifyDevice: failing to fix screen")
        return False

    if not checkSDCard(dm):
        log.info("verifyDevice: failing to check SD card")
        return False

    if not cleanupTegra(dm, doCheckStalled):
        log.info("verifyDevice: failing to cleanup tegra")
        return False
    
    if watcherINI:
        if not setWatcherINI(dm):
            log.info("verifyDevice: failing to set watcher.ini")
            return False

    return True

if __name__ == '__main__':
    tegra_name = os.getenv('SUT_NAME')
    if (len(sys.argv) <> 2):
        if tegra_name in (None, ''):
            print "usage: verify.py [tegra name]"
            print "   Must have $SUT_NAME set in environ to omit tegra name"
            sys.exit(1)
        else:
            log.info("INFO: Using tegra '%s' found in env variable" % tegra_name)
    else:
        tegra_name = sys.argv[1]
    
    if verifyDevice(tegra_name) == False:
        sys.exit(1) # Not ok to proceed

    sys.exit(0)
