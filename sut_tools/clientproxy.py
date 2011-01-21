#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import time
import atexit
import socket
import asyncore
import logging
import datetime
import traceback
import subprocess

from signal import SIGTERM
from optparse import OptionParser
from Queue import Empty
from multiprocessing import Process, Queue, current_process, get_logger, log_to_stderr


"""clientproxy.py

Manage a buildbot client/slave instance for each defined Android device.

    Parameters
        --bbpath   <path>       Parent directory where the Tegra buildslaves are located.
                                Used to set working directory for each buildslave started
        --tegras   <path/file>  Tegra proxy config file.  One entry per Tegra slave to manage.
                                Each Tegra entry can have an optional IP address.
        --debug                 Turn on debug logging
        --echo                  Turn on echoing of log output to the terminal
        --daemon                Behave as a daemon process.  Requires one of the following commands
                                to be present on the command line: start, stop or restart
        --logpath               Path where log file output is written
        --pidpath               Path where PID file is written
"""


log             = get_logger()
eventQueue      = Queue()
options         = None
slaveMgr        = None

sutDataPort     = 20700
sutDialbackPort = 20742
maxErrors       = 5

ourIP           = None
ourPID          = None
ourPath         = os.getcwd()
ourName         = os.path.splitext(os.path.basename(sys.argv[0]))[0]

defaultOptions = {
                   'debug':    ('-d', '--debug',    False,    'Enable Debug', 'b'),
                   'bbpath':   ('-p', '--bbpath',   ourPath,  'Path where the Tegra buildbot slave clients can be found'),
                   'tegras':   ('-t', '--tegras',   os.path.join(ourPath, 'tegras.txt'),  'List of Tegra buildslaves to manage'),
                   'logpath':  ('-l', '--logpath',  ourPath,  'Path where log file is to be written'),
                   'pidpath':  ('',   '--pidpath',  ourPath,  'Path where the pid file is to be created'),
                   'echo':     ('-e', '--echo',     False,    'Enable echoing of log output to stderr', 'b'),
                   'hangtime': ('',   '--hangtime', 1200,     'How long (in seconds) a slave can be idle'),
                 }


def dumpException(msg):
    """Gather information on the current exception stack and log it
    """
    t, v, tb = sys.exc_info()
    log.error(msg)
    for s in traceback.format_exception(t, v, tb):
        if '\n' in s:
            for t in s.split('\n'):
                log.error(t)
        else:
            log.error(s[:-1])
    log.error('Traceback End')

def loadOptions():
    """Parse command line parameters and return options object
    """
    global options, daemon, ourPID

    daemon  = None
    options = None
    parser  = OptionParser()

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

    fileHandler   = logging.FileHandler(os.path.join(options.logpath, '%s.log' % ourName))
    fileFormatter = logging.Formatter('%(asctime)s %(levelname)-7s %(processName)s: %(message)s')

    fileHandler.setFormatter(fileFormatter)

    log.addHandler(fileHandler)
    log.fileHandler = fileHandler

    if options.echo:
        echoHandler   = logging.StreamHandler()
        echoFormatter = logging.Formatter('%(levelname)-7s %(processName)s: %(message)s')

        echoHandler.setFormatter(echoFormatter)

        log.addHandler(echoHandler)
        log.info('echoing')

    if options.debug:
        log.setLevel(logging.DEBUG)
        log.info('debug level is on')

    pidFile = os.path.join(ourPath, '%s.pid' % ourName)
    ourPID = os.getpid()
    file(pidFile,'w+').write("%s\n" % ourPID)


def runCommand(cmd, env=None):
    """Execute the given command and logs stdout with stderr piped to stdout
    """
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    try:
        for item in p.stdout:
            log.info(item[:-1])
        p.wait()
    except KeyboardInterrupt:
        p.kill()
        p.wait()

    return p

def getLastLine(filename):
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
            if len(s) > 0:
                result = s
                break
            n -= 1

    return result

def getOurIP():
    result = None

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('mozilla.com', 80))
        result = s.getsockname()[0]
        s.close()
    except:
        dumpException('unable to determine our IP address')

    return result

class DialbackHandler(asyncore.dispatcher_with_send):
    def __init__(self, sock, events):
        asyncore.dispatcher_with_send.__init__(self, sock)

        self.events = events

    def handle_read(self):
        data = self.recv(1024)
        log.info('data: %s' % data)

        if data.startswith('register '):
            self.send('OK\n')
            ip  = self.addr[0].strip()
            self.events.put((ip, 'dialback'))

class DialbackServer(asyncore.dispatcher):
    def __init__(self, host, port, events):
        asyncore.dispatcher.__init__(self)

        self.events = events
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        log.info('Binding to %s port %d' % (host, port))
        self.bind((host, port))
        self.listen(5)

    def handle_accept(self):
        log.info('incoming request')
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            log.info('Connection from %s' % repr(addr))
            handle = DialbackHandler(sock, self.events)

def handleDialback(port, events):
    """Dialback listener
    The SUTAgent will 'ping' our address/port when it first starts.
    
    This DialbackHandler method will be called for an incoming Tegra's ping
    when the listener is connected to by SUTAgent.
    
    NOTE: This code should only be run in it's own thread/process
          as it will not return
    """
    log.info('listener starting')
    dialback = DialbackServer('0.0.0.0', port, events)
    while asyncore.socket_map:
        try:
            asyncore.loop(timeout=1, count=1)
        except:
            dumpException('error during dialback loop')
            break

def checkSlave(slave, bbclient):
    pidfile = os.path.join(bbclient, 'twistd.pid')

    try:
        pid = int(file(pidfile, 'r').read().strip())
    except:
        dumpException('unable to check slave - pidfile [%s] was not readable' % pidfile)
        return False

    try:
        os.kill(pid, 0)
    except OSError:
        dumpException('check to see if pid %s is active failed')
        return False

    logFile  = os.path.join(bbclient, 'twistd.log')
    lastline = getLastLine(logFile)

    if len(lastline) > 0:
        logTS = datetime.datetime.strptime(lastline[:19], '%Y-%m-%d %H:%M:%S')
        logTD = datetime.datetime.now() - logTS

        if logTD.days > 0 or (logTD.days == 0 and logTD.seconds > slave['hangtime']):
            log.error('%s: tail of %s shows last activity was %d days %d seconds ago - marking as hung slave' % 
                      (slave['tag'], logFile, logTD.days, logTD.seconds))
            return False
        else:
            log.debug('%s: last activity was %d days %d seconds ago' % 
                      (slave['tag'], logTD.days, logTD.seconds))

    return True

def killPID(tag, piddfile, signal='15'):
    try:
        pid = file(pidFile,'r').read().strip()
    except IOError:
        log.info('unable to read %s pidfile [%s]' % (tag, pidFile))
        return False

    log.warning('%s pidfile found.  sending SIGTERM to %s' % (tag, pid))

    runCommand(['kill', '-%s' % signal, pid])
    time.sleep(90)

    try:
        os.kill(pid, 0)
    except OSError:
        dumpException('check to see if pid %s is active failed')
        return False

    return True

def stopSlave(slave, bbpath, events):
    bbclient = os.path.join(bbpath, slave['tag'])
    pidFile  = os.path.join(bbclient, 'twistd.pid')

    log.info('stopping buildbot in %s' % bbclient)

    runCommand(['buildslave', 'stop', bbclient])

    time.sleep(90)

    if os.path.exists(pidFile):
        if not killPID(slave['tag'], pidFile):
            if not killPID(slave['tag'], pidfile, signal='9'):
                log.warning('%s: unable to stop buildslave' % slave['tag'])

    events.put((slave['tag'], 'removed'))

def monitorSlave(slave, bbpath, slaveMgr, events):
    """Slave monitoring task/process
    Each active slave will have a monitoring process spawned.
    
    The monitoring process will open a socket to the monitoring port and
    listen for the heartbeat signal.
    
    If the signal is present, then the buildslave instance for that Tegra
    will be active.
    
    If the signal is not present, then the buildslave instance will not
    be active.
    
    For any exception or error, just terminate the monitor process loop
    and let the event manager restart it.
    """
    monitoring = True
    bbActive   = False
    hbActive   = False
    hbRepeats  = 0
    maxRepeats = 10    # how many "normal" logs to skip
    maxFails   = 200   # how many heartbeat errors to allow
    hbFails    = 0     # current number of hearbeat fails
    maxReq     = 9     # how sutAgent debug calls to skip
    infoReq    = maxReq
    bbclient   = os.path.join(bbpath, slave['tag'])
    pidFile    = os.path.join(bbclient, 'twistd.pid')
    flagFile   = os.path.join(bbclient, 'proxy.flg')
    bbEnv      = { 'PATH':     os.getenv('PATH'),
                   'SUT_NAME': slave['tag'],
                   'SUT_IP':   slave['ip'],
                 }

    lastHangCheck = time.time()

    log.info('monitoring started: pid [%s]' % current_process().pid)

    while monitoring:
        try:
            hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            hbSocket.settimeout(float(120))
            hbSocket.connect((slave['ip'], slave['port']))
            connected = True
        except:
            log.error('Error connecting to data port (%s of %s)' % (hbFails, maxFails))
            connected = False
            hbFails  += 1
            time.sleep(10)

        while connected:
            hbFails = 0

            try:
                if infoReq == 0:
                    log.debug('gathering debug data')
                    hbSocket.send('info\n')
                    infoReq = maxReq
                infoReq -= 1

                if hbRepeats == 0:
                    log.debug('listening for heartbeat')
                data = hbSocket.recv(1024)
                hbActive = True

                if len(data) > 1:
                    if hbRepeats == 0:
                        log.debug('socket data [%s]' % data[:-1])

                    if 'hump thump' in data or 'trace' in data:
                        if hbRepeats == 0:
                            log.info('heartbeat detected')
                    elif 'ebooting ...' in data:
                        log.warning('device is rebooting')
                        if not os.path.isfile(flagFile):
                            hbActive = False
                else:
                    time.sleep(10)

                if hbActive:
                    if slaveMgr.checkReboot(slave['tag']):
                        log.info('hbActive and reboot flag found')
                        os.remove(flagFile)

                    if bbActive and not os.path.isfile(pidFile):
                        bbActive = False
                        log.error('buildbot client pidfile not found')

                    if bbActive:
                        n = time.time()
                        if int(n - lastHangCheck) > 300:
                            lastHangCheck = n
                            if not checkSlave(slave, bbclient):
                                monitoring = False
                                break
                    else:
                        bbProc = runCommand(['buildslave', 'start', bbclient], env=bbEnv)

                        if bbProc is not None and bbProc.returncode >= 0:
                            bbActive = True

            except socket.timeout:
                log.error('socket timeout while monitoring')
                hbActive = False

                if slaveMgr.checkReboot(slave['tag']):
                    log.info('socket timeout but reboot flag present, looping')
                else:
                    connected = False
            except Exception as e:
                dumpException('exception during monitoring')
                hbActive = False

                if slaveMgr.checkReboot(slave['tag']):
                    log.info('socket exception but reboot flag present, looping')
                else:
                    connected = False

            if hbRepeats == 0:
                log.debug('hbActive %s bbActive %s ' % (hbActive, bbActive))

            if bbActive and not hbActive:
                if os.path.isfile(flagFile) or slaveMgr.checkReboot(slave['tag']):
                    log.info('proxy.flg found - looping monitor')
                else:
                    monitoring = False
                    break

            if hbActive:
                hbRepeats += 1
                if hbRepeats > maxRepeats:
                    hbRepeats = 0
            else:
                hbRepeats = 0

        if connected:
            hbSocket.close()
        else:
            if not os.path.isfile(flagFile):
                log.error('heartbeat is not active - stopping monitor loop')
                break

        if hbFails > maxFails:
            break

    if bbActive:
        events.put((slave['tag'], 'stop'))

    log.info('monitoring stopped')


class SlaveManager(object):
    def __init__(self):
        self.monitors    = {}
        self.slaveList   = {}
        self.rebootList  = []
        self.lastRefresh = None

    def clearMonitor(self, tag):
        if tag in self.monitors:
            log.info('monitor process for %s cleared' % tag)

            self.monitors[tag].terminate()
            self.monitors[tag].join()
            del self.monitors[tag]

            self.slaveList[tag]['state'] = 'unknown'

        if tag in self.rebootList:
            self.rebootList.remove(tag)

    def findTag(self, ip):
        result = None
        for tag in self.slaveList:
            if self.slaveList[tag]['ip'] == ip:
                result = tag
                break
        return result

    def markRebooted(self, tag):
        if tag not in self.rebootList:
            self.rebootList.append(tag)

    def checkReboot(self, tag, newValue=None):
        if newValue is not None:
            if newValue:
                if tag not in self.rebootList:
                    self.rebootList.append(tag)
            else:
                if tag in self.rebootList:
                    self.rebootList.remove(tag)
        return tag in self.rebootList

    def checkSlaves(self, events):
        for tag in self.slaveList.keys():
            if tag in self.monitors:
                if self.monitors[tag] is None and self.slaveList[tag]['state'] != 'reset':
                    log.error('monitor process for %s has died - restarting' % tag)
                    self.slaveList[tag]['errors'] += 1
                    self.slaveList[tag]['state']   = 'reset'
                    events.put((tag, 'stop'))
                else:
                    if not self.monitors[tag].is_alive() and self.slaveList[tag]['state'] != 'reset':
                        log.error('monitor process for %s is not alive - resetting. pid = %s' % (tag, self.monitors[tag].pid))
                        self.slaveList[tag]['errors'] += 1
                        self.slaveList[tag]['state']   = 'reset'
                        events.put((tag, 'stop'))

    def loadSlaves(self, events):
        """Determine the list of Tegra slaves
        The list of slaves to manage is determined by the entries in the
        Tegra config file.

        For each slave initialize the state and insert a 'start' state
        into the event queue.

        Tegra config file format:
          <tag> <ip>
        """
        log.info('Checking for changes in [%s]' % options.tegras)

        newList = {}
        if os.path.isfile(options.tegras):
            for line in open(options.tegras, 'r').readlines():
                if len(line) > 0 and line[0] not in ('#', ';'):
                    item = line[:-1].split()

                    if len(item) > 0:
                        s  = item[0]
                        ip = None

                        if len(item) == 2:
                            ip = item[1]

                        if s not in self.slaveList or self.slaveList[s]['state'] == 'unknown':
                            self.slaveList[s] = { 'state':    'unknown',
                                                  'ip':       ip,
                                                  'tag':      s,
                                                  'port':     sutDataPort,
                                                  'errors':   0,
                                                  'hangtime': options.hangtime,
                                                 }
                            log.info('%s added to pool' % s)
                            events.put((s, 'start'))

                        newList[s] = ip

        keys = newList.keys()

        for s in self.slaveList:
            if s in keys:
                ip = self.slaveList[s]['ip']
                if newList[s] != ip:
                    log.info('%s found in device list, but with different IP: %s -> %s - restarting'% (s, ip, newList[s]))
                    self.slaveList[s]['ip'] = newList[s]
                    events.put((s, 'restart'))
            else:
                log.info('%s not found in device list - removing' % s)
                events.put((s, 'delete'))

        self.lastRefresh = os.path.getmtime(options.tegras)


def eventLoop(events, slaveMgr):
    """Event Manager
    A state machine that has the following states:
    
      unknown, idle,
      reset, stop, start,
      reboot,
      error, remove
    
    Ignore any Tegra proxy that has been in an error state for
    maxErrors tries.
    """
    log.debug('starting eventLoop')

    stopMonitors = {}

    slaveMgr.loadSlaves(events)

    while True:
        try:
            item = events.get(False)
            if item is not None:
                tag, newState = item

                if tag in slaveMgr.slaveList:
                    slave = slaveMgr.slaveList[tag]
                    state = slave['state']

                    slave['state'] = newState

                    if slave['errors'] > maxErrors:
                        slave['state'] = 'error'
                        log.error('%s: has been in an error state for %d attempts, skipping' % (tag, maxErrors))
                        continue

                    log.info('%s: Changing state %s --> %s' % (tag, state, newState))
                    if newState == 'stop':
                        slaveMgr.clearMonitor(tag)

                    elif newState == 'start':
                        if tag in slaveMgr.monitors and slaveMgr.monitors[tag] is not None:
                            log.info('%s: has a monitor process, looping' % tag)
                            continue

                        if slave['ip'] is None:
                            try:
                                addrinfo    = socket.getaddrinfo(tag, slave['port'])
                                slave['ip'] = addrinfo[4][0]
                                log.info('%s: IP is %s' % (tag, slave['ip']))
                            except:
                                dumpException('%s: error during IP lookup' % tag)
                                continue

                        slave['errors'] = 0

                        slaveMgr.monitors[tag] = Process(name=tag, target=monitorSlave, args=(slave, options.bbpath, slaveMgr, events))
                        slaveMgr.monitors[tag].start()

                        log.info('%s: monitor process created. pid %s' % (tag, slaveMgr.monitors[tag].pid))

                    elif newState == 'restart':
                        slaveMgr.clearMonitor(tag)
                        events.put((tag, 'start'))

                    elif newState == 'delete':
                        if tag in stopMonitors:
                            log.error('%s: a prior attempt to stop slave found - shutting that one down')
                            stopMonitors[tag].terminate()
                            stopMonitors[tag].join()
                            del stopMonitors[tag]

                        stopMonitors[tag] = Process(name='%s stop' % tag, target=stopSlave, args=(slave, options.bbpath, events))
                        stopMonitors[tag].start()

                        log.info('%s: delete process created. pid %s' % (tag, stopMonitors[tag].pid))

                    elif newState == 'removed':
                        if tag in stopMonitors:
                            stopMonitors[tag].terminate()
                            stopMonitors[tag].join()
                            del stopMonitors[tag]
                        log.info('%s: removed from poll' % tag)
                else:
                    if newState == 'dialback':
                        ip  = tag
                        tag = slaveMgr.findTag(ip)

                        if tag is None:
                            log.error('unknown IP %s pinged the dialback listener' % ip)
                        else:
                            log.info('%s: dialback ping from tegra' % tag)
                            flagFile = os.path.join(options.bbpath, tag, 'proxy.flg')
                            if os.path.isfile(flagFile):
                                log.info('%s: proxy.flg found - skipping restart because we are in installApp phase' % tag)
                                slaveMgr.markRebooted(tag)
                            else:
                                log.info('%s: setting monitor state to start' % tag)
                                events.put((tag, 'start'))

        except Empty:
            time.sleep(5)

            if os.path.getmtime(options.tegras) > slaveMgr.lastRefresh:
                slaveMgr.loadSlaves(events)

            slaveMgr.checkSlaves(events)

            if len(stopMonitors) > 0:
                log.warning('stopMonitor has the following active: %s' % (','.join(stopMonitors.keys())))

    log.debug('leaving eventLoop')

if __name__ == '__main__':
    ourIP = getOurIP()

    if ourIP is None:
        log.error('our IP address is not defined, exiting')
        sys.exit(1)

    loadOptions()
    slaveMgr = SlaveManager()

    try:
        Process(name='dialback', target=handleDialback, args=(sutDialbackPort, eventQueue)).start()
        Process(name='eventloop', target=eventLoop, args=(eventQueue, slaveMgr)).start()
        # eventLoop(eventQueue)
        while True:
            time.sleep(0.5)
    finally:
        for tag in slaveMgr.slaveList.keys():
            slaveMgr.clearMonitor(tag)
