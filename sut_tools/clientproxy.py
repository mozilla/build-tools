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

def checkSlave(tag, bbClient, hangtime):
    pidfile = os.path.join(bbClient, 'twistd.pid')

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

    logFile  = os.path.join(bbClient, 'twistd.log')
    lastline = getLastLine(logFile)

    if len(lastline) > 0:
        logTS = datetime.datetime.strptime(lastline[:19], '%Y-%m-%d %H:%M:%S')
        logTD = datetime.datetime.now() - logTS

        if logTD.days > 0 or (logTD.days == 0 and logTD.seconds > hangtime):
            log.error('tail of %s shows last activity was %d days %d seconds ago - marking as hung slave' % 
                      (logFile, logTD.days, logTD.seconds))
            return False
        else:
            log.debug('last activity was %d days %d seconds ago' % (logTD.days, logTD.seconds))

    return True

def killPID(tag, pidFile, signal='2'):
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
        time.sleep(20)

    log.debug('pid check: %d' % n)
    if n > 9:
        log.error('check to see if pid %s is active failed')
        return False
    else:
        return True

def stopSlave(tag, pidFile):
    log.info('stopping buildbot')

    if os.path.exists(pidFile):
        log.debug('pidfile found, attempting to kill')
        if not killPID(tag, pidFile):
            if not killPID(tag, pidFile, signal='9'):
                log.warning('unable to stop buildslave')

    return os.path.exists(pidFile)

def monitorSlave(slave):
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
    log.info('monitoring started (pid [%s])' % current_process().pid)

    events     = slave['queue']
    tag        = slave['tag']
    sutIP      = slave['ip']
    sutPort    = slave['port']
    bbPath     = slave['bbpath']
    bbClient   = os.path.join(bbPath,   tag)
    pidFile    = os.path.join(bbClient, 'twistd.pid')
    flagFile   = os.path.join(bbClient, 'proxy.flg')
    errorFile  = os.path.join(bbClient, 'error.flg')
    bbEnv      = { 'PATH':     os.getenv('PATH'),
                   'SUT_NAME': tag,
                   'SUT_IP':   sutIP,
                 }

    hbSocket      = None
    hbActive      = False
    bbActive      = False
    nextState     = None
    connected     = False
    inReboot      = False
    lastHangCheck = time.time()

    hbRepeats  = 0
    hbFails    = 0
    infoReq    = 0
    maxRepeats = 10    # how many "normal" logs to skip
    maxFails   = 200   # how many heartbeat errors to allow
    maxReq     = 9     # how sutAgent debug calls to skip

    while True:
        try:
            nextState = events.get(False)
        except Empty:
            nextState = None

        if nextState is not None:
            log.debug('state %s -> %s' % (slave['state'], nextState))
            if nextState == 'start':
                if hbActive:
                    if not bbActive:
                        log.debug('starting buildslave in %s' % bbClient)
                        bbProc = runCommand(['twistd', '--no_save',
                                                       '--rundir=%s' % bbClient,
                                                       '--pidfile=%s' % pidFile,
                                                       '--python=%s' % os.path.join(bbClient, 'buildbot.tac')], env=bbEnv)
                        bbActive = False
                        if bbProc is not None:
                            log.info('buildslave start returned %d' % bbProc.returncode)
                            if bbProc.returncode == 0 or bbProc.returncode == 1:
                                bbActive = True
                    else:
                        log.debug('buildslave already running')

                    if bbActive:
                        hbFails = 0
                        events.put('running')

            elif nextState == 'stop':
                if bbActive:
                    if stopSlave(tag, pidFile):
                        events.put('stop')
                    else:
                        events.put('offline')
                    bbActive = False

            elif nextState == 'offline':
                if bbActive:
                    stopSlave(tag, pidFile)
                bbActive = False

            elif nextState == 'terminate':
                log.warning('terminate request received - exiting monitor loop')
                break

            elif nextState == 'dialback':
                    log.info('dialback ping from tegra')
                    if os.path.isfile(flagFile):
                        log.info('proxy flag found - skipping restart because we are in installApp phase')
                        inReboot = False
                        events.put('running')
                    else:
                        if os.path.isfile(errorFile):
                            log.warning('error flag found - not allowing dialback to trigger a start')
                            events.put('offline')
                        else:
                            if inReboot:
                                inReboot = False
                                events.put('running')
                            else:
                                log.info('restarting')
                                events.put('start')

            slave['state'] = nextState

        if not connected:
            try:
                hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                hbSocket.settimeout(float(120))
                hbSocket.connect((sutIP, sutPort))
                connected = True
            except:
                connected = False
                hbFails  += 1
                if hbRepeats == 0 or hbFails > (maxFails - 10):
                    log.debug('Error connecting to data port (%s of %s)' % (hbFails, maxFails))

        log.debug('state %s connected %s hbActive %s bbActive %s' %
                  (slave['state'], connected, hbActive, bbActive))

        if connected:
            try:
                if infoReq == 0:
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
                        inReboot = True
                        log.warning('device is rebooting')
                        events.put('rebooting')
                        if not os.path.isfile(flagFile):
                            hbActive = False

                if hbActive and slave['state'] in ('init',):
                    events.put('start')

                if bbActive:
                    if os.path.isfile(pidFile):
                        n = time.time()
                        if int(n - lastHangCheck) > 300:
                            lastHangCheck = n
                            if not checkSlave(tag, bbClient, slave['hangtime']):
                                events.put('offline')
                    else:
                        log.error('buildbot client pidfile not found')
                        events.put('offline')

            except socket.timeout:
                hbActive  = False
                connected = False
                log.warning('socket timeout while monitoring')

            except Exception as e:
                hbActive  = False
                connected = False
                if e.errno == 54:  # Connection reset by peer
                    log.warning('socket reset by peer')
                else:
                    dumpException('exception during monitoring')

            if hbRepeats == 0:
                log.debug('hbActive %s bbActive %s ' % (hbActive, bbActive))

            if bbActive and not hbActive:
                if os.path.isfile(flagFile) or inReboot:
                    inReboot = True
                else:
                    events.put('stop')

            if hbActive:
                hbFails    = 0
                hbRepeats += 1
                if hbRepeats > maxRepeats:
                    hbRepeats = 0
            else:
                hbRepeats = 0

        if not hbActive:
            if inReboot:
                log.debug('heartbeat not active but reboot flag present, looping')
            time.sleep(10)

        if slave['state'] == 'offline':
            hbFails = 0
            time.sleep(10)

        f = os.path.isfile(errorFile)
        if hbFails > maxFails or f:
            events.put('offline')
            if f:
                log.error('error flag detected')
            else:
                log.error('heartbeat failure limit exceeded')

    if connected:
        hbSocket.close()

    if bbActive:
        stopSlave(tag, pidFile)

    log.info('monitor stopped')


class SlaveManager(object):
    def __init__(self):
        self.slaveList   = {}
        self.lastRefresh = None

    def findTag(self, ip):
        result = None
        for tag in self.slaveList:
            if self.slaveList[tag]['ip'] == ip:
                result = tag
                break
        return result

    def loadSlaves(self, events):
        """Determine the list of Tegra slaves
        The list of slaves to manage is determined by the entries in the
        Tegra config file.

        For each slave initialize a monitor object

        Tegra config file format:
          <tag> <ip>
        """
        log.info('Checking for changes in [%s]' % options.tegras)

        newList = {}
        if os.path.isfile(options.tegras):
            for line in open(options.tegras, 'r').readlines():
                if len(line) > 0 and line[0] not in ('#', ';'):
                    entry = line[:-1].split()

                    if len(entry) > 0:
                        tag = entry[0]
                        ip  = None

                        if len(entry) == 2:
                            ip = entry[1]

                        if tag not in self.slaveList:
                            self.slaveList[tag] = { 'state':    'unknown',
                                                    'ip':       ip,
                                                    'tag':      tag,
                                                    'port':     sutDataPort,
                                                    'mgr':      self,
                                                    'errors':   0,
                                                    'bbpath':   options.bbpath,
                                                    'hangtime': options.hangtime,
                                                  }
                            slave = self.slaveList[tag]

                            slave['queue']   = Queue()
                            slave['monitor'] = Process(name=tag, target=monitorSlave, args=(slave,))

                            slave['monitor'].start()
                            slave['queue'].put('init')

                            log.info('%s: monitor process created (pid %s)' % (tag, slave['monitor'].pid))

                        newList[tag] = ip

        keys = newList.keys()

        for tag in self.slaveList:
            if tag in keys:
                ip = self.slaveList[tag]['ip']
                if newList[tag] != ip:
                    log.info('%s found in device list, but with different IP: %s -> %s - restarting'% (tag, ip, newList[tag]))
                    self.slaveList[tag]['ip'] = newList[tag]
                    self.slaveList[tag]['queue'].put((tag, 'restart'))
            else:
                log.info('%s: not found in device list - removing' % tag)
                self.slaveList[tag]['queue'].put((tag, 'offline'))

        self.lastRefresh = os.path.getmtime(options.tegras)


def eventLoop(events, slaveMgr):
    log.debug('starting')

    slaveMgr.loadSlaves(events)

    while True:
        try:
            item = events.get(False)
            if item is not None:
                tag, newState = item

                if newState == 'dialback':
                    ip  = tag
                    tag = slaveMgr.findTag(ip)

                    if tag is None:
                        log.error('unknown IP %s pinged the dialback listener' % ip)
                    else:
                        slave = slaveMgr.slaveList[tag]
                        slave['queue'].put(newState)

        except Empty:
            time.sleep(5)

            if os.path.getmtime(options.tegras) > slaveMgr.lastRefresh:
                slaveMgr.loadSlaves(events)

    log.debug('leaving')


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
