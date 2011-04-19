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
from sut_lib import checkSlaveAlive, checkSlaveActive, getIPAddress, dumpException, loadOptions, \
                    checkCPAlive, checkCPActive, getLastLine, stopProcess


log            = logging.getLogger()
options        = None
exportHandle   = None
defaultOptions = {
                   'debug':  ('-d', '--debug',  False,     'Enable Debug', 'b'),
                   'bbpath': ('-p', '--bbpath', '/builds', 'Path where the Tegra buildbot slave clients can be found'),
                   'tegra':  ('-t', '--tegra',  None,      'Tegra to check, if not given all Tegras will be checked'),
                   'reset':  ('-r', '--reset',  False,     'Reset error.flg if Tegra active', 'b'),
                   'master': ('-m', '--master', 'sp',      'master type to check "p" for production or "s" for staging'),
                   'export': ('-e', '--export', False,     'export summary stats (disabled if -t present)', 'b'),
                 }


def checkTegra(master, tegra):
    tegraIP    = getIPAddress(tegra)
    tegraPath  = os.path.join(options.bbpath, tegra)
    exportFile = os.path.join(tegraPath, '%s_status.log' % tegra)
    errorFile  = os.path.join(tegraPath, 'error.flg')
    proxyFile  = os.path.join(tegraPath, 'proxy.flg')

    status = { 'active':    False,
               'cp':        False,
               'bs':        False,
               'tegra':     tegra,
               'msg':       '',
             }

    log.debug('%s: %s' % (tegra, tegraIP))

    errorFlag = os.path.isfile(errorFile)
    proxyFlag = os.path.isfile(proxyFile)

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
        sTegra = 'online'
    else:
        sTegra = 'OFFLINE'

    if checkCPAlive(tegraPath):
        logTD = checkCPActive(tegraPath)
        if logTD is not None and logTD.days > 0 or (logTD.days == 0 and logTD.seconds > 300):
            status['cp']   = 'INACTIVE'
            status['msg'] += 'CP %dd %ds;' % (logTD.days, logTD.seconds)
        else:
            status['cp'] = 'active'
    else:
        status['cp'] = 'OFFLINE'

    if checkSlaveAlive(tegraPath):
        logTD = checkSlaveActive(tegraPath)
        if logTD is not None and logTD.days > 0 or (logTD.days == 0 and logTD.seconds > 3600):
            status['bs']   = 'INACTIVE'
            status['msg'] += 'BS %dd %ds;' % (logTD.days, logTD.seconds)
        else:
            status['bs'] = 'active'
    else:
        status['bs'] = 'OFFLINE'

    if errorFlag:
        status['msg'] += 'error.flg [%s] ' % getLastLine(errorFile)
    if proxyFlag:
        status['msg'] += 'REBOOTING '

    s = '%s %s %8s %8s %8s :: %s' % (status['tegra'], master, sTegra, status['cp'], status['bs'], status['msg'])
    log.info(s)
    open(exportFile, 'a+').write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), s))
    if options.export:
        hSummary.write('%s\n' % s)

    if options.reset:
        stopProcess(os.path.join(tegraPath, 'twistd.pid'), 'buildslave')

        try:
            hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            hbSocket.settimeout(float(120))
            hbSocket.connect((tegraIP, 20700))
            hbSocket.send('rebt\n')
            hbSocket.close()
            log.info('rebooting tegra')
        except:
            dumpException('socket')

        if errorFlag:
            log.info('clearing error.flg')
            os.remove(errorFile)
        if proxyFlag:
            log.info('clearing proxy.flg')
            os.remove(proxyFile)


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
        options.export = False
        tegras.append(options.tegra)

    f = True
    for tegra in tegras:
        m = findMaster(tegra)
        if m in options.master:
            if f:
                if options.export:
                    hSummary = open(os.path.join(options.bbpath, 'tegra_status.txt'), 'w+')
                log.info('%9s %s %8s %8s %8s :: %s' % ('Tegra ID', 'M', 'Tegra', 'CP', 'Slave', 'Msg'))
                f = False

            checkTegra(m, tegra)

    if options.export and hSummary is not None:
        hSummary.close()

