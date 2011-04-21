#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import time
import datetime
import socket
import signal
import logging
import traceback
import subprocess

from optparse import OptionParser
# from multiprocessing import get_logger, log_to_stderr


log = logging.getLogger()


def dumpException(msg):
    """Gather information on the current exception stack and log it
    """
    t, v, tb = sys.exc_info()
    log.debug(msg)
    for s in traceback.format_exception(t, v, tb):
        if '\n' in s:
            for t in s.split('\n'):
                log.debug(t)
        else:
            log.debug(s[:-1])
    log.debug('Traceback End')

def runCommand(cmd, env=None, logEcho=True):
    """Execute the given command.
    Sends to the logger all stdout and stderr output.
    """
    log.debug('calling [%s]' % ' '.join(cmd))

    o = []
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    try:
        for item in p.stdout:
            o.append(item[:-1])
            if logEcho:
                log.debug(item[:-1])
        p.wait()
    except KeyboardInterrupt:
        p.kill()
        p.wait()

    return p, o

def getOurIP(hostname='bm-remote.build.mozilla.org'):
    """Open a socket against a known server to discover our IP address
    """
    if 'CP_IP' in os.environ:
        result = os.environ['CP_IP']
    else:
        result = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((hostname, 80))
            result = s.getsockname()[0]
            s.close()
        except:
            dumpException('unable to determine our IP address')
    return result

def getIPAddress(hostname):
    """Parse the output of nslookup to determine what is the
    IP address for the tegra ID that is to be monitored.
    """
    ipAddress = None
    f         = False
    p, o      = runCommand(['nslookup', hostname], logEcho=False)
    for s in o:
        if '**' in s:
            break
        if f:
            if s.startswith('Address:'):
                ipAddress = s.split()[1]
        else:
            if s.startswith('Name:'):
                f = True

    return ipAddress

def getChildPIDs(pid):
    #ps -U cltbld -O ppid,pgid,command
    #pid   ppid  pgid
    #18456     1 18455 /opt/local/Libra   ??  S      0:00.88 /opt/local/Library/Frameworks/Python.framework/Versions/2.6/Resources/Python.app/Contents/MacOS/Python /opt/local/Library/Frameworks/Python.framework/Versions/2.6/bin/twistd$
    #18575 18456 18455 /opt/local/Libra   ??  S      0:00.52 /opt/local/Library/Frameworks/Python.framework/Versions/2.6/Resources/Python.app/Contents/MacOS/Python ../../sut_tools/installApp.py 10.250.49.8 ../talos-data/fennec-4.1a1pr$
    p, lines = runCommand(['ps', '-U', 'cltbld', '-O', 'ppid,pgid,command'])
    pids = []
    for line in lines:
        item = line.split()
        if len(item) > 1:
            try:
                p = int(item[1])
                if p == pid:
                    pids.append(int(item[0]))
            except ValueError:
                pass
    return pids

def killPID(pid, signal=signal.SIGTERM, includeChildren=False):
    """Attempt to kill a process.
    After sending signal, confirm if process is 
    """
    log.info('calling kill for pid %s with signal %s' % (pid, signal))
    if includeChildren:
        childList = getChildPIDs(pid)
        for childPID in childList:
            killPID(childPID, signal, True)
    try:
        os.kill(pid, signal)
        n = 0
        while n < 30:
            n += 1
            try:
                # verify process is gone
                os.kill(pid, 0)
                time.sleep(1)
            except OSError:
                return True
        return False
    except OSError:
        # if pid doesn't exist, then it worked ;)
        return True

def getLastLine(filename):
    """Run the tail command against the given file and return
    the last non-empty line.
    The content of twistd.log often has output from the slaves
    so we can't assume that it will always be non-empty line.
    """
    result   = ''
    fileTail = []

    if os.path.isfile(filename):
        p = subprocess.Popen(['tail', filename], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            for item in p.stdout:
                fileTail.append(item)
            p.wait()
        except KeyboardInterrupt:
            p.kill()
            p.wait()

    if len(fileTail) > 0:
        n = len(fileTail) - 1
        while n >= 0:
            s = fileTail[n].strip()
            if len(s) > 4 and len(s[:4].strip()) > 0:
                result = s
                break
            n -= 1

    return result

def stopProcess(pidFile, label):
    log.debug('looking for %s' % pidFile)
    if os.path.isfile(pidFile):
        try:
            pid = int(open(pidFile, 'r').read().strip())
            log.debug('first attempt to kill %s' % pid)
            if not killPID(pid, includeChildren=True):
                log.debug('second attempt to kill %s' % pid)
                killPID(pid, signal=signal.SIGKILL, includeChildren=True)
            try:
                log.debug('verifying %s is gone' % label)
                try:
                    os.kill(pid, 0)
                except OSError:
                    log.info('%s stopped' % label)
                    os.remove(pidFile)
            except:
                dumpException('verify step of stopProcess')
                log.error('%s: pid %s not found' % (label, pid))
        except ValueError:
            log.error('unable to read %s' % pidFile)

def stopSlave(pidFile):
    """Try to terminate the buildslave
    """
    stopProcess(pidFile, 'buildslave')
    return os.path.exists(pidFile)

def checkSlaveAlive(bbClient):
    """Check if the buildslave process is alive.
    """
    pidFile = os.path.join(bbClient, 'twistd.pid')
    log.debug('checking if slave is alive [%s]' % pidFile)
    if os.path.isfile(pidFile):
        try:
            pid = int(file(pidFile, 'r').read().strip())
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                dumpException('check to see if pid %s is active failed' % pid)
        except:
            dumpException('unable to check slave - pidfile [%s] was not readable' % pidFile)
    return False

def checkSlaveActive(bbClient):
    """Check to determine what was the date/time
    of the last line of it's log output.
    """
    logFile  = os.path.join(bbClient, 'twistd.log')
    lastline = getLastLine(logFile)
    if len(lastline) > 0:
        logTS  = datetime.datetime.strptime(lastline[:19], '%Y-%m-%d %H:%M:%S')
        logTD  = datetime.datetime.now() - logTS
        return logTD
    return None

def checkCPAlive(bbClient):
    """Check if the clientproxy process is alive.
    """
    pidFile = os.path.join(bbClient, 'clientproxy.pid')
    log.debug('checking if clientproxy is alive [%s]' % pidFile)
    if os.path.isfile(pidFile):
        try:
            pid = int(file(pidFile, 'r').read().strip())
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                dumpException('check to see if pid %s is active failed' % pid)
        except:
            dumpException('unable to check clientproxy - pidfile [%s] was not readable' % pidFile)
    return False

def checkCPActive(bbClient):
    """Check to determine what was the date/time
    of the last line of it's log output.
    """
    logFile  = os.path.join(bbClient, 'clientproxy.log')
    lastline = getLastLine(logFile)
    if len(lastline) > 0:
        logTS  = datetime.datetime.strptime(lastline[:19], '%Y-%m-%d %H:%M:%S')
        logTD  = datetime.datetime.now() - logTS
        return logTD
    return None

# helper routines for interacting with devicemanager
# and buildslave steps

def setFlag(flagfile, contents=None):
    print(flagfile)
    h = open(flagfile, 'a+')
    if contents is not None:
        print(contents)
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

def getResolution(dm):
    parts  = dm.getInfo('screen')['screen'][0].split()
    width  = int(parts[0].split(':')[1])
    height = int(parts[1].split(':')[1])
    return width, height

def getDeviceTimestamp(dm):
    ts = int(dm.getCurrentTime()) # epoch time in milliseconds
    dt = datetime.datetime.utcfromtimestamp(ts / 1000)
    print("Current device time is %s" % dt.strftime('%Y/%m/%d %H:%M:%S'))
    return dt

def setDeviceTimestamp(dm):
    s = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    print("Setting device time to %s" % s)
    dm.sendCMD(['settime %s' % s])

def checkDeviceRoot(dm):
    dr = dm.getDeviceRoot()
    # checking for /mnt/sdcard/...
    print("devroot %s" % str(dr))
    if not dr or dr == '/tests':
        return None
    return dr

def waitForDevice(dm, waitTime=60):
    print("Waiting for tegra to come back...")
    time.sleep(waitTime)
    tegraIsBack = False
    tries       = 0
    maxTries    = 20
    while tries <= maxTries:
        tries += 1
        print("Try %d" % tries)
        if checkDeviceRoot(dm) is not None:
            tegraIsBack = True
            break
        time.sleep(waitTime)
    if not tegraIsBack:
        print("Remote Device Error: waiting for tegra timed out.")
        sys.exit(1)

def loadOptions(defaults=None):
    """Parse command line parameters and populate the options object.
    """
    parser = OptionParser()

    if defaults is not None:
        for key in defaults:
            items = defaults[key]

            if len(items) == 4:
                (shortCmd, longCmd, defaultValue, helpText) = items
                optionType = 's'
            else:
                (shortCmd, longCmd, defaultValue, helpText, optionType) = items

            if optionType == 'b':
                parser.add_option(shortCmd, longCmd, dest=key, action='store_true', default=defaultValue, help=helpText)
            else:
                parser.add_option(shortCmd, longCmd, dest=key, default=defaultValue, help=helpText)

    (options, args) = parser.parse_args()
    options.args    = args

    return options

