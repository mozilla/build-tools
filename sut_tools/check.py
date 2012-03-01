#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import time
import json
import socket
import signal
import logging
import datetime

# from multiprocessing import get_logger, log_to_stderr
from sut_lib import checkSlaveAlive, checkSlaveActive, getIPAddress, dumpException, loadOptions, \
                    checkCPAlive, checkCPActive, getLastLine, stopProcess, runCommand, pingTegra, \
                    reboot_tegra, stopTegra, getMaster


log            = logging.getLogger()
options        = None
oSummary       = None
defaultOptions = {
                   'debug':  ('-d', '--debug',  False,     'Enable Debug', 'b'),
                   'bbpath': ('-p', '--bbpath', '/builds', 'Path where the Tegra buildbot slave clients can be found'),
                   'tegra':  ('-t', '--tegra',  None,      'Tegra to check, if not given all Tegras will be checked'),
                   'reset':  ('-r', '--reset',  False,     'Reset error.flg if Tegra active', 'b'),
                   'reboot': ('-c', '--cycle',  False,     'Power cycle the Tegra', 'b'),
                   'master': ('-m', '--master', 'sp',      'master type to check "p" for production or "s" for staging'),
                   'export': ('-e', '--export', True,      'export summary stats (disabled if -t present)', 'b'),
                 }


def summary(tegra, master, sTegra, sCP, sBS, msg, timestamp, masterHost):
    if options.export:
        ts = timestamp.split()  # assumes "yyyy-mm-dd hh:mm:ss"
        d = { 'tegra':        tegra,
              'master':       master,
              'masterHost':   masterHost,
              'hostname':     options.hostname,
              'date':         ts[0],
              'time':         ts[1],
              'sTegra':       sTegra,
              'sClientproxy': sCP,
              'sSlave':       sBS,
              'msg':          msg,
            }
        oSummary.append(d)

def checkTegra(master, tegra):
    tegraIP    = getIPAddress(tegra)
    tegraPath  = os.path.join(options.bbpath, tegra)
    exportFile = os.path.join(tegraPath, '%s_status.log' % tegra)
    errorFile  = os.path.join(tegraPath, 'error.flg')
    proxyFile  = os.path.join(tegraPath, 'proxy.flg')
    errorFlag  = os.path.isfile(errorFile)
    proxyFlag  = os.path.isfile(proxyFile)
    sTegra     = 'OFFLINE'
    sutFound   = False
    logTD      = None

    status = { 'tegra':  tegra,
               'active': False,
               'cp':     'OFFLINE',
               'bs':     'OFFLINE',
               'msg':    '',
             }

    log.debug('%s: %s' % (tegra, tegraIP))

    if master is None:
        status['environment'] = 's'
        status['master']      = 'localhost'
    else:
        status['environment'] = master['environment'][0]
        status['master']      = 'http://%s:%s' % (master['hostname'], master['http_port'])

    fPing, lPing = pingTegra(tegra)
    if fPing:
        try:
            hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            hbSocket.settimeout(float(120))
            hbSocket.connect((tegraIP, 20700))

            sutFound = True

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
            sTegra = 'INACTIVE'

        if not sutFound:
            status['msg'] += 'SUTAgent not present;'
    else:
        status['msg'] += '%s %s;' % (lPing[0], lPing[1])

    if checkCPAlive(tegraPath):
        logTD = checkCPActive(tegraPath)
        if logTD is not None:
            if (logTD.days > 0) or (logTD.days == 0 and logTD.seconds > 300):
                status['cp']   = 'INACTIVE'
                status['msg'] += 'CP %dd %ds;' % (logTD.days, logTD.seconds)
            else:
                status['cp'] = 'active'
        else:
            status['cp'] = 'INACTIVE'
    else:
        if os.path.isfile(os.path.join(tegraPath, 'clientproxy.pid')):
            status['msg'] += 'clientproxy.pid found;'

    if checkSlaveAlive(tegraPath):
        logTD = checkSlaveActive(tegraPath)
        if logTD is not None:
            if (logTD.days > 0) or (logTD.days == 0 and logTD.seconds > 3600):
                status['bs']   = 'INACTIVE'
                status['msg'] += 'BS %dd %ds;' % (logTD.days, logTD.seconds)
            else:
                status['bs'] = 'active'
        else:
            status['bs'] = 'INACTIVE'
    else:
        # scan thru tegra-### dir and see if any buildbot.tac.bug#### files exist
        # but ignore buildbot.tac file itself (except to note that it is missing)
        files = os.listdir(tegraPath)
        found = False
        for f in files:
            if f.startswith('buildbot.tac'):
                found = True
                if len(f) > 12:
                    status['msg'] += '%s;' % f
        if not found:
            status['msg'] += 'buildbot.tac NOT found;'

    if errorFlag:
        status['msg'] += 'error.flg [%s] ' % getLastLine(errorFile)
    if proxyFlag:
        status['msg'] += 'REBOOTING '

    s  = '%s %s %9s %8s %8s :: %s' % (status['tegra'], status['environment'], sTegra, status['cp'], status['bs'], status['msg'])
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    log.info(s)
    open(exportFile, 'a+').write('%s %s\n' % (ts, s))
    summary(status['tegra'], status['environment'], sTegra, status['cp'], status['bs'], status['msg'], ts, status['master'])

    if errorFlag and options.reset:
        stopProcess(os.path.join(tegraPath, 'twistd.pid'), 'buildslave')

        if not options.reboot:
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

        # here we try to catch the state where sutagent and cp are inactive
        # that is determined by : sTegra == 'INACTIVE' and status['cp'] == 'INACTIVE'
        # status['cp'] will be set to INACTIVE only if logTD.seconds (last time clientproxy
        # updated it's log file) is > 3600
    if options.reboot:
        if not sutFound and status['bs'] != 'active':
            log.info('power cycling tegra')
            reboot_tegra(tegra)
        else:
            if sTegra == 'OFFLINE' and status['bs'] != 'active':
                log.info('power cycling tegra')
                reboot_tegra(tegra)

    if options.reset and sTegra == 'INACTIVE' and status['cp'] == 'INACTIVE':
        log.info('stopping hung clientproxy')
        stopTegra(tegra)
        time.sleep(5)
        log.info('starting clientproxy for %s' % tegra)
        os.chdir(tegraPath)
        runCommand(['python', 'clientproxy.py', '-b', '--tegra=%s' % tegra])

def findMaster(tegra):
    result  = None
    tacFile = os.path.join(options.bbpath, tegra, 'buildbot.tac')

    if os.path.isfile(tacFile):
        lines = open(tacFile).readlines()
        for line in lines:
            #buildmaster_host = 'dev-master01.build.scl1.mozilla.com'
            if line.startswith('buildmaster_host = '):
                v, h  = line.split('=')
                h     = h.strip().replace("'", "").replace('"', '')
                result = getMaster(h)
                break

    return result

def getHostname():
    result = 'unknown'
    p, o   = runCommand(['hostname',], logEcho=False)
    if len(o) > 0:
        result = o[0]
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

    tegras           = []
    options.bbpath   = os.path.abspath(options.bbpath)
    options.master   = options.master.lower()
    options.hostname = getHostname()

    if options.tegra is None:
        for f in os.listdir(options.bbpath):
            if os.path.isdir(os.path.join(options.bbpath, f)) and 'tegra-' in f.lower():
                tegras.append(f)
    else:
        options.export = False
        tegras.append(options.tegra)

    f = True
    for tegra in tegras:
        o = findMaster(tegra)
        if o is not None and o['environment'] == 'production':
            m = 'p'
        else:
            m = 's'
        if m in options.master:
            if f:
                if options.export:
                    oSummary = []
                log.info('%9s %s %8s %8s %8s :: %s' % ('Tegra ID', 'M', 'Tegra', 'CP', 'Slave', 'Msg'))
                f = False

            checkTegra(o, tegra)

    if options.export and oSummary is not None:
        h = open(os.path.join(options.bbpath, 'tegra_status.txt'), 'w+')
        h.write(json.dumps(oSummary))
        h.close()

