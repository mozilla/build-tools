#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import time
import socket
import logging
import traceback
import subprocess

from multiprocessing import Process, get_logger, log_to_stderr
from optparse import OptionParser


log            = logging.getLogger()
options        = None
defaultOptions = {
                   'debug':  ('-d', '--debug',  False,     'Enable Debug', 'b'),
                   'bbpath': ('-p', '--bbpath', '/builds', 'Path where the Tegra buildbot slave clients can be found'),
                   'tegra':  ('-t', '--tegra',  None,      'Tegra to check, if not given all Tegras will be checked'),
                   'reset':  ('-r', '--reset',  False,     'Reset error.flg if Tegra active', 'b'),
                 }


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

def killPID(pidFile, signal='2'):
    """Attempt to kill a process.
    First try to give the pid SIGTERM and if not succesful
    then use SIGKILL.
    """
    try:
        pid = file(pidFile,'r').read().strip()
    except IOError:
        log.info('unable to read pidfile [%s]' % pidFile)
        return False

    log.warning('pidfile found - sending kill -%s to %s' % (signal, pid))

    runCommand(['kill', '-%s' % signal, pid])

    n = 0
    while n < 10:
        try:
            os.kill(int(pid), 0)
            break
        except OSError:
            n += 1
        time.sleep(5)

    log.debug('pid check: %d' % n)
    if n > 9:
        log.error('check to see if pid %s is active failed')
        return False
    else:
        return True

def loadOptions():
    """Parse command line parameters and populate the options object.
    Optionally daemonize our parent process.
    """
    global options

    parser = OptionParser()

    for key in defaultOptions:
        items = defaultOptions[key]

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

    options.bbpath = os.path.abspath(options.bbpath)

    echoHandler   = logging.StreamHandler()
    echoFormatter = logging.Formatter('%(message)s')  # not the normal one

    echoHandler.setFormatter(echoFormatter)

    log.addHandler(echoHandler)

    if options.debug:
        log.setLevel(logging.DEBUG)
        log.info('debug level is on')
    else:
        log.setLevel(logging.INFO)

def getTegraIP(tegra):
    """Parse the output of nslookup to determine what is the
    IP address for the tegra ID that is to be monitored.
    """
    ipAddress = None
    f         = False
    p, o      = runCommand(['nslookup', tegra])
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

def checkTegra(tegra):
    tegraIP   = getTegraIP(tegra)
    errorFile = os.path.join(options.bbpath, tegra, 'error.flg')
    proxyFile = os.path.join(options.bbpath, tegra, 'proxy.flg')

    log.debug('%s: %s' % (tegra, tegraIP))

    try:
        hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hbSocket.settimeout(float(120))
        hbSocket.connect((tegraIP, 20700))

        time.sleep(2)

        hbSocket.send('info\n')

        d = hbSocket.recv(4096)

        log.debug('socket data length %d' % len(d))
        log.debug(d)

        if len(d) > 0:
            result = True
    except:
        dumpException('socket')
        result = False

    s = tegra

    if result:
        s += ' active'

        if os.path.isfile(errorFile):
            s += ' error.flg found'

            if options.reset:
                s += ' - resetting'
                os.remove(errorFile)
    else:
        s += ' OFFLINE'
        if os.path.isfile(errorFile):
            s += ' error.flg found'
        elif os.path.isfile(proxyFile):
            s += ' proxy.flg found (maybe rebooting?)'

    log.info(s)

if __name__ == '__main__':
    loadOptions()

    tegras = []
    if options.tegra is None:
        for f in os.listdir(options.bbpath):
            if os.path.isdir(os.path.join(options.bbpath, f)) and 'tegra-' in f.lower():
                tegras.append(f)
    else:
        tegras.append(options.tegra)

    for tegra in tegras:
        Process(name='check', target=checkTegra, args=(tegra,)).start()

