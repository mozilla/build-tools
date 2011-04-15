#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import time
import socket
import signal
import logging
import datetime

# from multiprocessing import get_logger, log_to_stderr
from sut_lib import checkSlaveAlive, checkSlaveActive, getIPAddress, dumpException, loadOptions, getLastLine, killPID


log            = logging.getLogger()
options        = None
defaultOptions = {
                   'debug':  ('-d', '--debug',  False,     'Enable Debug', 'b'),
                   'bbpath': ('-p', '--bbpath', '/builds', 'Path where the Tegra buildbot slave clients can be found'),
                   'tegra':  ('-t', '--tegra',  None,      'Tegra to check, if not given all Tegras will be checked'),
                   'reset':  ('-r', '--reset',  False,     'Reset error.flg if Tegra active', 'b'),
                   'master': ('-m', '--master', 'sp',      'master type to check "p" for production or "s" for staging'),
                 }


def checkTegra(master, tegra):
    tegraIP   = getIPAddress(tegra)
    tegraPath = os.path.join(options.bbpath, tegra)
    errorFile = os.path.join(tegraPath, 'error.flg')
    proxyFile = os.path.join(tegraPath, 'proxy.flg')

    status = { 'active':    False,
               'error.flg': False,
               'proxy.flg': False,
               'tegra':     tegra,
               'rebooted':  False,
             }

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

        status['active'] = True

        hbSocket.close()
    except:
        status['active'] = False
        dumpException('socket')

    if status['active']:
        s = 'online'
    else:
        s = 'OFFLINE'

    status['error.flg'] = os.path.isfile(errorFile)
    status['proxy.flg'] = os.path.isfile(proxyFile)

    if status['error.flg']:
        s += ' error.flg'
        status['error'] = getLastLine(errorFile)
    if status['proxy.flg']:
        s += ' rebooting'

    s = '%20s :: ' % s

    status['slave'] = checkSlaveAlive(tegraPath)

    if status['slave']:
        s += 'active'
    else:
        s += 'INACTIVE'

    logTD = checkSlaveActive(tegraPath)
    if logTD is not None:
        s += ' last was %d days %d seconds ago' % (logTD.days, logTD.seconds)
        if logTD.days > 0 or (logTD.days == 0 and logTD.seconds > 3600):
            s += ' (hung slave)'

    if status['error.flg']:
        s += ' :: %s' % status['error']

    log.info('%s %s %s' % (status['tegra'], master, s))

    if options.reset:
        s = ''
        if os.path.isfile(errorFile):
            s += ' clearing error.flg;'
            os.remove(errorFile)

            try:
                hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                hbSocket.settimeout(float(120))
                hbSocket.connect((tegraIP, 20700))
                hbSocket.send('rebt\n')
                hbSocket.close()
                status['rebooted'] = True
            except:
                dumpException('socket')

        if status['rebooted']:
            s += ' rebooting tegra;'

        if status['slave']:
            pidFile = os.path.join(tegraPath, 'twistd.pid')
            try:
                pid = int(open(pidFile).read())
                if not killPID(pid, includeChildren=True):
                    killPID(pid, signal=signal.SIGKILL, includeChildren=True)
                if not checkSlaveAlive(tegraPath):
                    s += ' buildslave stopped;'
                else:
                    s += ' tried to stop buildslave;'
            except ValueError:
                s += ' unable to read twistd.pid;'

        if len(s) > 0:
            log.info('%s: %s' % (status['tegra'], s[:-1]))

    return status

def findMaster(tegra):
    result  = 's'
    tacFile = os.path.join(options.bbpath, tegra, 'buildbot.tac')

    if os.path.isfile(tacFile):
        lines = open(tacFile).readlines()
        for line in lines:
            if line.startswith('buildmaster_host = '):
                if 'foopy' not in line:
                    result = 'p'
                    break

    return result

def initLogs(options):
    echoHandler   = logging.StreamHandler()
    echoFormatter = logging.Formatter('%(asctime)s %(message)s')  # not the normal one

    echoHandler.setFormatter(echoFormatter)
    log.addHandler(echoHandler)

    if options.debug:
        log.setLevel(logging.DEBUG)
        log.info('debug level is on')
    else:
        log.setLevel(logging.INFO)

if __name__ == '__main__':
    options = loadOptions(defaultOptions)
    initLogs(options)

    tegras         = []
    options.bbpath = os.path.abspath(options.bbpath)
    options.master = options.master.lower()

    if options.tegra is None:
        for f in os.listdir(options.bbpath):
            if os.path.isdir(os.path.join(options.bbpath, f)) and 'tegra-' in f.lower():
                tegras.append(f)
    else:
        tegras.append(options.tegra)

    for tegra in tegras:
        m = findMaster(tegra)
        if m in options.master:
            status = checkTegra(m, tegra)

