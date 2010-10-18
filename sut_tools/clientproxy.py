#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import time
import atexit
import socket
import logging
import traceback
import subprocess

from signal import SIGTERM
from optparse import OptionParser
from Queue import Empty
from multiprocessing import Process, Queue, current_process, freeze_support, get_logger, log_to_stderr


"""clientproxy.py

Manage a buildbot client/slave instance for each defined Android device.

The list of slaves to manage is pulled from config.py's android device list.

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


log            = get_logger()
options        = None
daemon         = None
slaveList      = {}
monitors       = {}
eventQueue     = Queue()
monitorQueue   = Queue()
sutDataPort    = 20700
maxErrors      = 5
lastRefresh    = None

ourPID         = None
ourPath        = os.getcwd()
ourName        = os.path.splitext(os.path.basename(sys.argv[0]))[0]

defaultOptions = {
                   'debug':   ('-d', '--debug',   False,    'Enable Debug', 'b'),
                   'bbpath':  ('-p', '--bbpath',  ourPath,  'Path where the Tegra buildbot slave clients can be found'),
                   'tegras':  ('-t', '--tegras',  os.path.join(ourPath, 'tegras.txt'),  'List of Tegra buildslaves to manage'),
                   'logpath': ('-l', '--logpath', ourPath,  'Path where log file is to be written'),
                   'pidpath': ('',   '--pidpath', ourPath,  'Path where the pid file is to be created'),
                   'echo':    ('-e', '--echo',    False,    'Enable echoing of log output to stderr', 'b'),
                   'daemon':  ('',   '--daemon',  False,    'Behave as a daemon.  Requires one of the following commands: start, stop, restart', 'b'),
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

    if options.daemon:
        cmdFound = False

        for s in args:
            if s.lower() in ('start', 'stop', 'restart'):
                cmdFound = True
                daemon   = forkMe(os.path.join(ourPath, '%s.pid' % ourName))
                if s == 'start':
                    daemon.start()
                elif s == 'stop':
                    daemon.stop()
                elif s == 'restart':
                    daemon.restart()
                break

        if not cmdFound:
            log.warning('Daemonize requested but no valid commands found - ignoring request')

    if daemon is not None:
        ourPID = daemon.ourPID
    else:
        ourPID = os.getpid()


class forkMe:
    """UNIX style daemonize using classic Stevens' method found in
    "Advanced Programming in the UNIX Environment"
    """
    def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self.stdin   = stdin
        self.stdout  = stdout
        self.stderr  = stderr
        self.pidfile = pidfile
        self.ourPID  = None

    def daemonize(self):
        try:
            if os.fork() > 0:
                sys.exit(0)
        except OSError:
            log.error('unable to daemonize (pre-fork)')
            sys.exit(1)

        os.chdir("/")
        os.setsid()
        os.umask(0)

        try:
            if os.fork() > 0:
                sys.exit(0)
        except OSError, e:
            log.error('unable to daemonize (detach fork)')
            sys.exit(1)

        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self.stdin,  'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        atexit.register(self.exitCleanup)
        self.ourPID = os.getpid()

        file(self.pidfile,'w+').write("%s\n" % self.ourPID)

    def exitCleanup(self):
        os.remove(self.pidfile)

    def start(self):
        pid = None
        try:
            pid = int(file(self.pidfile,'r').read().strip())
        except IOError:
            pid = None

        if pid is not None:
            log.info('PID file [%s] already present so we are assumed to be active.  Clear PID file if this is not the case' % self.pidfile)
            sys.exit(1)

        log.info('attempting to daemonize our process')
        self.daemonize()
        self.run()

    def stop(self):
        pid = None
        try:
            pid = int(file(self.pidfile,'r').read().strip())
        except IOError:
            pid = None

        if not pid:
            log.info('PID file [%s] not found. Shutting down.')
            sys.exit()
        else:
            try:
                while 1:
                    os.kill(pid, SIGTERM)
                    time.sleep(0.1)
            except OSError:
                log.info('PID %s terminated, shutting down'% pid)

            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)

        sys.exit()

    def restart(self):
        self.stop()
        self.start()

    def run(self):
        pass


def loadSlaves():
    """Determine the list of Tegra slaves
    The list of slaves to manage is determined by the entries in the
    Tegra config file.
    
    For each slave initialize the state and insert a 'start' state
    into the event queue.
    """
    global lastRefresh

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

                    if s not in slaveList:
                        slaveList[s] = { 'state':  'idle',
                                         'ip':     ip,
                                         'tag':    s,
                                         'port':   sutDataPort,
                                         'errors': 0,
                                       }
                        log.info('%s added to pool' % s)
                        eventQueue.put((s, 'start'))

                    newList[s] = ip

    keys = newList.keys()

    for s in slaveList:
        if s in keys:
            if newList[s] != slaveList[s]['ip']:
                log.info('%s found in device list, but with different IP: %s -> %s - restarting'% (s, slaveList[s]['ip'], newList[s]))
                slaveList[s]['ip'] = newList[s]
                eventQueue.put((s, 'stop'))
        else:
            log.info('%s not found in device list - removing' % s)
            eventQueue.put((s, 'delete'))

    lastRefresh = os.path.getmtime(options.tegras)

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

def monitorSlave(slave, bbpath, parentPID):
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
    bbActive = False
    hbActive = False
    bbclient = os.path.join(bbpath, slave['tag'])
    pidFile  = os.path.join(bbclient, 'twistd.pid')
    bbEnv    = { 'PATH':     os.getenv('PATH'),
                 'SUT_NAME': slave['tag'],
                 'SUT_IP':   slave['ip'],
               }

    log.info('monitoring started: pid [%s]' % current_process().pid)

    try:
        hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hbSocket.settimeout(float(120))
        hbSocket.connect((slave['ip'], slave['port']))
        connected = True
    except:
        dumpException('error connecting to data port')
        connected = False

    while connected:
        if os.getppid() != parentPID:
            log.error('parent process has gone away, shutting down monitoring')
            break

        try:
            log.debug('listening for heartbeat')
            data = hbSocket.recv(1024)
            log.debug('socket data [%s]' % data[:-1])

            if 'hump thump' in data or 'trace' in data:
                log.debug('heartbeat detected')
                hbActive = True
            elif 'ebooting ...' in data:
                log.info('device is rebooting')
                hbActive = False
            else:
                log.debug('heartbeat not found')
                hbActive = False

            if hbActive:
                if bbActive:
                    if not os.path.isfile(pidFile):
                        bbActive = False
                        log.error('buildbot client pidfile not found')
                else:
                    bbProc = runCommand(['buildslave', 'start', bbclient], env=bbEnv)

                    if bbProc is not None and bbProc.returncode >= 0:
                        bbActive = True

        except socket.timeout:
            log.error('socket timeout while monitoring')
            connected = False
        except Exception as e:
            dumpException('exception during monitoring')
            connected = False

        log.debug('hbActive %s bbActive %s' % (hbActive, bbActive))

        if not bbActive or not hbActive:
            break

    if connected:
        hbSocket.close()

    if bbActive:
        log.info('stopping buildbot client in %s' % bbclient)
        runCommand(['buildslave', 'stop', bbclient], env=bbEnv)

    log.info('monitoring stopped')

def clearMonitor(tag):
    if tag in monitors:
        log.info('shutting down monitor for %s' % tag)
        pidfile = os.path.join(options.bbpath, tag, 'twistd.pid')

        if os.path.exists(pidfile):
            try:
                n   = 10
                pid = int(file(pidfile,'r').read().strip())
                try:
                    while n > 0:
                        os.kill(pid, SIGTERM)
                        time.sleep(0.2)
                        n -= 1
                except OSError:
                    log.info('%s buildbot slave terminated' % tag)
            except IOError:
                log.info('unable to read pidfile [%s] for %s' % (pidfile, tag))

        monitors[tag].terminate()
        monitors[tag].join()
        del monitors[tag]

def eventLoop():
    """Event Manager
    basically it's a simple state machine that has the following
    possible states: idle, reset, stop, start, error, remove
    
    Ignore any Tegra proxy that has been in an error state for
    maxErrors tries.
    """
    while True:
        try:
            item = eventQueue.get(False)
            if item is not None:
                tag, newState = item
                slave = slaveList[tag]
                state = slave['state']

                slave['state'] = newState

                if slave['errors'] > maxErrors:
                    slave['state'] = 'error'
                    log.error('%s has been in an error state for %d attempts, skipping' % (tag, maxErrors))
                    continue

                log.info('Changing state for %s: %s --> %s' % (tag, state, newState))
                if newState == 'stop':
                    clearMonitor(tag)
                    # TODO add code to verify that any child PIDs are actually stopped
                    eventQueue.put((tag, 'start'))

                elif newState == 'start':
                    if tag in monitors and monitors[tag] is not None:
                        log.debug('%s has a monitor process, setting state to stop' % tag)
                        eventQueue.put((tag, 'stop'))
                        continue

                    if slave['ip'] is None:
                        try:
                            addrinfo    = socket.getaddrinfo(tag, slave['port'])
                            slave['ip'] = addrinfo[4][0]
                            log.info('IP for %s is %s' % (tag, slave['ip']))
                        except:
                            dumpException('error during IP lookup for %s' % tag)
                            continue

                    slave['errors'] = 0

                    monitors[tag] = Process(name=tag, target=monitorSlave, args=(slave, options.bbpath, ourPID))
                    monitors[tag].start()

                    log.info('monitor process for %s created. pid %s errors %s' % (tag, monitors[tag].pid, slave['errors']))
                elif newState == 'delete':
                    clearMonitor(tag)
                    del slaveList[tag]
                    log.debug('%s removed from poll' % tag)

        except Empty:
            time.sleep(5)

            if os.path.getmtime(options.tegras) > lastRefresh:
                loadSlaves()

            for tag in slaveList.keys():
                if tag in monitors:
                    if monitors[tag] is None and slaveList[tag]['state'] != 'reset':
                        log.error('monitor process for %s has died - restarting' % tag)
                        slaveList[tag]['errors'] += 1
                        slaveList[tag]['state']   = 'reset'
                        eventQueue.put((tag, 'stop'))
                    else:
                        if not monitors[tag].is_alive() and slaveList[tag]['state'] != 'reset':
                            log.error('monitor process for %s is not alive - resetting. pid = %s' % (tag, monitors[tag].pid))
                            slaveList[tag]['errors'] += 1
                            slaveList[tag]['state']   = 'reset'
                            eventQueue.put((tag, 'stop'))


if __name__ == '__main__':
    loadOptions()
    loadSlaves()
    try:
        eventLoop()
    finally:
        for tag in slaveList.keys():
            clearMonitor(tag)
