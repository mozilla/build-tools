#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import socket
import signal
import logging

from sut_lib import loadOptions, getIPAddress, stopProcess, checkSlaveAlive, dumpException


options        = None
log            = logging.getLogger()
defaultOptions = {
                   'debug':  ('-d', '--debug',  False,     'Enable debug output', 'b'),
                   'bbpath': ('-p', '--bbpath', '/builds', 'Path where the Tegra buildbot slave clients can be found'),
                   'tegra':  ('-t', '--tegra',  None,      'Tegra to check, if not given all Tegras will be checked'),
                 }


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

def stopTegra(tegra):
    tegraIP   = getIPAddress(tegra)
    tegraPath = os.path.join(options.bbpath, tegra)
    errorFile = os.path.join(tegraPath, 'error.flg')
    proxyFile = os.path.join(tegraPath, 'proxy.flg')

    log.info('%s: %s - stopping all processes' % (tegra, tegraIP))

    stopProcess(os.path.join(tegraPath, 'clientproxy.pid'), 'clientproxy')
    stopProcess(os.path.join(tegraPath, 'twistd.pid'), 'buildslave')

    log.debug('  clearing flag files')

    if os.path.isfile(errorFile):
        log.info('  error.flg cleared')
        os.remove(errorFile)

    if os.path.isfile(proxyFile):
        log.info('  proxy.flg cleared')
        os.remove(proxyFile)

    log.debug('  sending rebt to tegra')

    try:
        hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hbSocket.settimeout(float(120))
        hbSocket.connect((tegraIP, 20700))
        hbSocket.send('rebt\n')
        hbSocket.close()
    except:
        log.error('  tegra socket error')


if __name__ == '__main__':
    options = loadOptions(defaultOptions)
    initLogs(options)

    options.bbpath = os.path.abspath(options.bbpath)

    if options.tegra is None:
        log.error('you must specify a single Tegra')
        sys.exit(2)

    stopTegra(options.tegra)

