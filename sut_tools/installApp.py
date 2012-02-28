#!/usr/bin/env python

import os, sys
import glob, shutil, zipfile
import time
import random
import socket
import datetime
import devicemanagerSUT as devicemanager

from sut_lib import getOurIP, calculatePort, clearFlag, setFlag, checkDeviceRoot, \
                    getDeviceTimestamp, setDeviceTimestamp, \
                    getResolution, waitForDevice, runCommand


# hwine: minor ugg - the flag files need to be global. Refactoring into
#        a class would solve, but this module is scheduled for rewrite


def installOneApp(dm, devRoot, app_file_local_path):

    source       = app_file_local_path
    filename     = os.path.basename(source)
    target       = os.path.join(devRoot, filename)

    global proxyFile, errorFile

    print "Installing %s" % target
    if dm.pushFile(source, target):
        status = dm.installApp(target)
        if status is None:
            print '-'*42
            print 'installApp() done - gathering debug info'
            dm.getInfo('process')
            dm.getInfo('memory')
            dm.getInfo('uptime')
            try:
                print dm.sendCMD(['exec su -c "logcat -d -v time *:W"'])
            except devicemanager.DMError, e:
                print "Exception hit while trying to run logcat: %s" % str(e)
                setFlag(errorFile, "Remote Device Error: can't run logcat")
                sys.exit(1)
        else:
            clearFlag(proxyFile)
            setFlag(errorFile, "Remote Device Error: updateApp() call failed - exiting")
            sys.exit(1)

    else:
        clearFlag(proxyFile)
        setFlag(errorFile, "Remote Device Error: unable to push %s" % target)
        sys.exit(1)

def find_robocop():
    # we hardcode the relative path to robocop.apk for bug 715215
    # but it may not be unpacked at the time this runs, so be prepared
    # to extract if needed (but use the extracted one if there)
    extracted_location = 'build/tests/bin/robocop.apk'
    self_extracted_location = 'build/robocop.apk'
    actual_location = None

    # for better error reporting
    global proxyFile, errorFile

    if os.path.exists(extracted_location):
        actual_location = extracted_location
    elif os.path.exists(self_extracted_location):
        # already grabbed it in prior step
        actual_location = self_extracted_location
    else:
        expected_zip_location = 'build/fennec*tests.zip'
        matches = glob.glob(expected_zip_location)
        if len(matches) == 1:
            # try to grab the file we need from there, giving up if any
            # assumption doesn't match
            try:
                archive = zipfile.ZipFile(matches[0], 'r')
                apk_info = archive.getinfo('bin/robocop.apk')
                # it's in the archive, extract to tmp dir - will be created
                archive.extract(apk_info, 'build/tmp')
                shutil.move('build/tmp/bin/robocop.apk', self_extracted_location)
                actual_location = self_extracted_location
                # got it
            except Exception as e:
                print "WARNING (robocop): zip file not as expected: %s (%s)" % (e.message,
                                                                        str(e.args))
                print "WARNING (robocop): robocop.apk will not be installed"
        else:
            print "WARNING (robocop): Didn't find just one %s; found '%s'" % (expected_zip_location,
                                                                      str(matches))
            print "WARNING (robocop): robocop.apk will not be installed"

    return actual_location

def one_time_setup(ip_addr, major_source):
    ''' One time setup of state

    ip_addr - of the tegra we want to install app at
    major_source - we've hacked this script to install
            may-also-be-needed tools, but the source we're asked to
            install has the meta data we need

    Side Effects:
        We two globals, needed for error reporting:
            errorFile, proxyFile
    '''

    # set up the flag files, used throughout
    cwd       = os.getcwd()
    global proxyFile, errorFile
    proxyFile = os.path.join(cwd, '..', 'proxy.flg')
    errorFile = os.path.join(cwd, '..', 'error.flg')

    proxyIP   = getOurIP()
    proxyPort = calculatePort()

    workdir      = os.path.dirname(major_source)
    inifile      = os.path.join(workdir, 'fennec', 'application.ini')
    remoteappini = os.path.join(workdir, 'talos', 'remoteapp.ini')
    print 'copying %s to %s' % (inifile, remoteappini)
    runCommand(['cp', inifile, remoteappini])

    print "connecting to: %s" % ip_addr
    dm = devicemanager.DeviceManagerSUT(ip_addr)
# Moar data!
    dm.debug = 3

    devRoot  = checkDeviceRoot(dm)

    if devRoot is None or devRoot == '/tests':
        setFlag(errorFile, "Remote Device Error: devRoot from devicemanager [%s] is not correct - exiting" % devRoot)
        sys.exit(1)

    try:
        setFlag(proxyFile)
        print proxyIP, proxyPort
        getDeviceTimestamp(dm)
        setDeviceTimestamp(dm)
        getDeviceTimestamp(dm)
        dm.getInfo('process')
        dm.getInfo('memory')
        dm.getInfo('uptime')

        width, height = getResolution(dm)
        #adjust resolution down to allow fennec to install without memory issues
        if (width >= 1050 or height >= 1050):
            dm.adjustResolution(1024, 768, 'crt')
            print 'calling reboot'
            dm.reboot(proxyIP, proxyPort)
            waitForDevice(dm)

            width, height = getResolution(dm)
            if width != 1024 and height != 768:
                clearFlag(proxyFile)
                setFlag(errorFile, "Remote Device Error: Resolution change failed.  Should be %d/%d but is %d/%d" % (1024,768,width,height))
                sys.exit(1)

    finally:
        clearFlag(proxyFile)

    return dm, devRoot

def main(argv):
    if (len(argv) < 3):
      print "usage: installApp.py <ip address> <localfilename> [<processName>]"
      sys.exit(1)

    # N.B. 3rd arg not used anywhere
    if len(argv) > 3:
        processName = argv[3]
    else:
        processName = 'org.mozilla.fennec'

    ip_addr = argv[1]
    path_to_main_apk = argv[2]
    dm, devRoot = one_time_setup(ip_addr, path_to_main_apk)
    installOneApp(dm, devRoot, path_to_main_apk)
    # also install robocop if it's available
    robocop_to_use = find_robocop()
    if robocop_to_use is not None:
        waitForDevice(dm)
        installOneApp(dm, devRoot, robocop_to_use)

    # make sure we're all the way back up before we finish
    waitForDevice(dm)

if __name__ == '__main__':
    # Stop buffering! (but not while testing)
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

    main(sys.argv)
