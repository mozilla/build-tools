#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import socket
import signal

from sut_lib import loadOptions, getIPAddress, killPID, checkSlaveAlive


options        = None
defaultOptions = {
                   'bbpath': ('-p', '--bbpath', '/builds', 'Path where the Tegra buildbot slave clients can be found'),
                   'tegra':  ('-t', '--tegra',  None,      'Tegra to check, if not given all Tegras will be checked'),
                 }


def stopTegra(tegra):
    tegraIP   = getIPAddress(tegra)
    tegraPath = os.path.join(options.bbpath, tegra)
    errorFile = os.path.join(tegraPath, 'error.flg')
    proxyFile = os.path.join(tegraPath, 'proxy.flg')

    print('%s: %s - stopping all processes' % (tegra, tegraIP))

    pidFile = os.path.join(tegraPath, 'clientproxy.pid')
    if os.path.isfile(pidFile):
        try:
            pid = int(open(pidFile).read())
            if not killPID(pid, includeChildren=True):
                killPID(pid, signal=signal.SIGKILL, includeChildren=True)
            try:
                os.kill(pid, 0)
                print('  clientproxy stopped')
            except:
                print('  **** tried to stop clientproxy')
        except ValueError:
            print('  unable to read %s' % pidFile)

    pidFile = os.path.join(tegraPath, 'twistd.pid')
    if os.path.isfile(pidFile):
        try:
            pid = int(open(pidFile).read())
            if not killPID(pid, includeChildren=True):
                killPID(pid, signal=signal.SIGKILL, includeChildren=True)
            try:
                os.kill(pid, 0)
                print('  buildslave stopped')
            except:
                print('  **** tried to stop buildslave')
        except ValueError:
            print('  unable to read %s' % pidFile)

    if os.path.isfile(errorFile):
        print('  error.flg cleared')
        os.remove(errorFile)

    if os.path.isfile(proxyFile):
        print('  proxy.flg cleared')
        os.remove(proxyFile)

    try:
        hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hbSocket.settimeout(float(120))
        hbSocket.connect((tegraIP, 20700))
        hbSocket.send('rebt\n')
        hbSocket.close()
    except:
        print('  tegra socket error')


if __name__ == '__main__':
    options = loadOptions(defaultOptions)

    options.bbpath = os.path.abspath(options.bbpath)

    if options.tegra is None:
        print('you must specify a single Tegra')
        sys.exit(2)

    stopTegra(options.tegra)

