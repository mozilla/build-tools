#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import time
import pwd
import atexit
import signal
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
        --bbpath   <path>   Parent directory where the buildslave to control is located.
        --tegra             Tegra to manage. If not given it will be determined.
        --tegraIP           IP address of Tegra to manage. Will be discovered if not given.
        --debug             Turn on debug logging.
        --background        Fork to a daemon process.
        --logpath           Path where log file output is written.
        --pidpath           Path where PID file is written.
        --hangtime          Timeout value in seconds before a slave can be marked as hung.
"""


log             = get_logger()
eventQueue      = Queue()
options         = None
daemon          = None

sutDataPort     = 20700
sutDialbackPort = 42000 # base - tegra id # will be added to this
maxErrors       = 5

ourIP           = None
ourPath         = os.getcwd()
ourName         = os.path.splitext(os.path.basename(sys.argv[0]))[0]


defaultOptions = {
                   'debug':      ('-d', '--debug',      True,     'Enable Debug', 'b'),
                   'background': ('-b', '--background', False,    'daemonize ourselves', 'b'),
                   'bbpath':     ('-p', '--bbpath',     ourPath,  'Path where the Tegra buildbot slave clients can be found'),
                   'tegra':      ('-t', '--tegra',      None,     'Tegra to manage, if not given it will be figured out from environment'),
                   'tegraIP':    ('',   '--tegraIP',    None,     'IP of Tegra to manage, if not given it will found via nslookup'),
                   'logpath':    ('-l', '--logpath',    ourPath,  'Path where log file is to be written'),
                   'pidpath':    ('',   '--pidpath',    ourPath,  'Path where the pid file is to be created'),
                   'hangtime':   ('',   '--hangtime',   1200,     'How long (in seconds) a slave can be idle'),
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
    """Parse command line parameters and populate the options object.
    Optionally daemonize our parent process.
    """
    global options, sutDialbackPort

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

    fileHandler   = logging.FileHandler(os.path.join(options.logpath, '%s.log' % ourName))
    fileFormatter = logging.Formatter('%(asctime)s %(levelname)-7s %(processName)s: %(message)s')

    fileHandler.setFormatter(fileFormatter)

    log.addHandler(fileHandler)
    log.fileHandler = fileHandler

    if not options.background:
        echoHandler   = logging.StreamHandler()
        echoFormatter = logging.Formatter('%(levelname)-7s %(processName)s: %(message)s')

        echoHandler.setFormatter(echoFormatter)

        log.addHandler(echoHandler)
        log.info('echoing')

    if options.debug:
        log.setLevel(logging.DEBUG)
        log.info('debug level is on')

    if options.tegra is None:
        if 'tegra-' in ourPath.lower():
            options.tegra = os.path.basename(os.path.split(ourPath)[-1])

    if options.tegraIP is None:
        options.tegraIP = getTegraIP()

    try:
        n = int(options.tegra.split('-')[1])
    except:
        n = 0
    sutDialbackPort += n


class Daemon(object):
    def __init__(self, pidfile):
        self.stdin   = '/dev/null'
        self.stdout  = '/dev/null'
        self.stderr  = '/dev/null'
        self.pidfile = pidfile

    def handlesigterm(self, signum, frame):
        if self.pidfile is not None:
            try:
                eventQueue.put(('terminate',))
                os.remove(self.pidfile)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                pass
        sys.exit(0)

    def start(self):
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError, exc:
            sys.stderr.write("%s: failed to fork from parent: (%d) %s\n" % (sys.argv[0], exc.errno, exc.strerror))
            sys.exit(1)

        os.chdir("/")
        os.setsid()
        os.umask(0)

        try:
            pid = os.fork()
            if pid > 0:
                sys.stdout.close()
                sys.exit(0)
        except OSError, exc:
            sys.stderr.write("%s: failed to fork from parent #2: (%d) %s\n" % (sys.argv[0], exc.errno, exc.strerror))
            sys.exit(1)

        sys.stdout.flush()
        sys.stderr.flush()

        si = open(self.stdin, "r")
        so = open(self.stdout, "a+")
        se = open(self.stderr, "a+", 0)

        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        if self.pidfile is not None:
            open(self.pidfile, "wb").write(str(os.getpid()))

        signal.signal(signal.SIGTERM, self.handlesigterm)

    def stop(self):
        if self.pidfile is None:
            sys.exit("no pidfile specified")
        try:
            pidfile = open(self.pidfile, "rb")
        except IOError, exc:
            sys.exit("can't open pidfile %s: %s" % (self.pidfile, str(exc)))
        data = pidfile.read()
        try:
            pid = int(data)
        except ValueError:
            sys.exit("mangled pidfile %s: %r" % (self.pidfile, data))
        os.kill(pid, signal.SIGTERM)


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
                log.info(item[:-1])
        p.wait()
    except KeyboardInterrupt:
        p.kill()
        p.wait()

    return p, o

def getLastLine(filename):
    """Run the tail command against the given file and return
    the last non-empty line.
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
            if len(s) > 0:
                result = s
                break
            n -= 1

    return result

def getOurIP():
    """Open a socket against a known server to discover our IP address
    """
    result = None

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('bm-foopy.build.mozilla.org', 80))
        result = s.getsockname()[0]
        s.close()
    except:
        dumpException('unable to determine our IP address')

    return result

def getTegraIP():
    """Parse the output of nslookup to determine what is the
    IP address for the tegra ID that is to be monitored.
    """
    ipAddress = None
    f         = False
    p, o      = runCommand(['nslookup', options.tegra])
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
            self.events.put(('dialback', ip))

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
    dialback = DialbackServer('0.0.0.0', port, events)
    while asyncore.socket_map:
        try:
            asyncore.loop(timeout=1, count=1)
        except:
            dumpException('error during dialback loop')
            break

def checkSlave(bbClient, hangtime):
    """Check if the buildslave process is alive.
    If it is alive, then also check to determine what was the
    date/time of the last line of it's log output.
    
    Return False if it's not alive or if that last output was more
    than 0 days and the given hangtime seconds.
    """
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

def killPID(pid, signal='2'):
    """Attempt to kill a process.
    First try to give the pid SIGTERM and if not succesful
    then use SIGKILL.
    """
    log.info('calling kill for pid %s with signal %s' % (pid, signal))

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

def stopSlave(pidFile):
    """Try to terminate the buildslave
    """
    log.info('stopping buildbot')

    if os.path.exists(pidFile):
        log.debug('pidfile %s found' % pidFile)
        pid = file(pidFile,'r').read().strip()
        try:
            os.kill(int(pid), 0)
            log.debug('process found for pid %s, attempting to kill' % pid)
            if not killPID(pid):
                if not killPID(pid, signal='9'):
                    log.warning('unable to stop buildslave')
        except OSError:
            log.info('no process found for pid %s, removing pidfile' % pid)
            os.remove(pidFile)
    return os.path.exists(pidFile)

def sendReboot(ip, port):
    log.warning('sending rebt to tegra')
    try:
        hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hbSocket.settimeout(float(120))
        hbSocket.connect((ip, port))
        hbSocket.send('rebt\n')
        hbSocket.recv(4096)
    except:
        log.debug('Error sending reboot')

def monitorTegra(events):
    """Monitor the assigned Tegra.
    Endless loop that monitors the Tegra by trying to establish
    and read from the sutAgentAndroid's heartbeat port.
    
    If activity is found on the heartbeat port then send the 'active' event.
    """
    flagFile  = os.path.join(options.bbpath, 'proxy.flg')
    hbSocket  = None
    connected = False
    maxFails  = 75
    maxReq    = 9     # how sutAgent debug calls to skip
    infoReq   = maxReq
    logSpam   = 0
    hbFails   = 0
    sleepTime = 5

    log.info('%s: monitoring started' % options.tegra)

    while True:
        time.sleep(sleepTime)
        if not connected:
            try:
                hbSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                hbSocket.settimeout(float(120))
                hbSocket.connect((options.tegraIP, sutDataPort))
                connected = True
            except:
                connected = False
                hbFails  += 1
                log.debug('Error connecting to data port')

        if logSpam == 0:
            log.debug('connected %s hbFails: %d infoReq %d' % (connected, hbFails, infoReq))

        if connected:
            infoReq -= 1
            if infoReq == 0:
                infoReq = maxReq
                try:
                    hbSocket.send('info\n')
                except:
                    connected = False
                    hbFails  += 1

            if connected:
                try:
                    data = hbSocket.recv(1024)
                except:
                    data      = ''
                    connected = False
                    dumpException('hbSocket.recv()')

                if len(data) > 1:
                    log.debug('socket data [%s]' % data[:-1])

                    if 'ebooting ...' in data:
                        log.warning('device is rebooting')
                        events.put(('reboot',))
                    else:
                        sleepTime = 5
                        log.info('heartbeat detected')
                        events.put(('active',))
                else:
                    hbFails += 1

        if hbFails > maxFails:
            if os.path.isfile(flagFile):
                log.warning('install flag found, resetting error count')
            else:
                events.put(('offline',))
            if connected:
                hbSocket.close()
                connected = False
            hbFails    = 0
            sleepTime += 5
            if sleepTime > 60:
                sleepTime = 60

        if logSpam == 0:
            logSpam = 5
        else:
            logSpam -= 1

    log.info('%s: monitoring stopped' % options.tegra)

def monitorEvents():
    """This is the main state machine for the Tegra monitor.

    Respond to the events sent via queue and also monitor the
    state of the buildslave if it's been started.
    """
    pidFile   = os.path.join(options.bbpath, 'twistd.pid')
    flagFile  = os.path.join(options.bbpath, 'proxy.flg')
    errorFile = os.path.join(options.bbpath, 'error.flg')
    bbEnv     = { 'PATH':     os.getenv('PATH'),
                  'SUT_NAME': options.tegra,
                  'SUT_IP':   options.tegraIP,
                }

    event         = None
    bbActive      = False
    tegraActive   = False
    softCount     = 0    # how many times tegraActive is True
                         # but errorFlag is set
    softCountMax  = 5    # how many active events to wait bdfore
                         # triggering a soft reset
    softResets    = 0
    softResetMax  = 3    # how many soft resets do we try before
                         # waiting for a hard reset
    hardResets    = 0
    hardResetsMax = 3
    lastHangCheck = time.time()

    log.info('monitoring started (process pid %s)' % current_process().pid)

    while True:
        try:
            event = eventQueue.get(False)
        except Empty:
            event = None
            time.sleep(15)

        if event is not None:
            state = event[0]
            log.debug('event %s' % state)

            if state == 'reboot':
                tegraActive = False
                if not os.path.isfile(flagFile):
                    log.warning('Tegra rebooting, stopping buildslave')
                    eventQueue.put(('stop',))
            elif state == 'active' or state == 'dialback':
                tegraActive = True
                if not bbActive:
                    if os.path.isfile(errorFile):
                        log.warning('Tegra active but error flag set [%d/%d]' % (softCount, softResets))
                        softCount += 1
                        if softCount > softCountMax:
                            softCount = 0
                            if softResets < softResetMax:
                                softResets += 1
                                log.info('removing error flag to see if tegra comes back')
                                os.remove(errorFile)
                            else:
                                hardResets += 1
                                log.info('hard reset reboot check [%d/%d]' % (hardResets, hardResetsMax))
                                if hardResets < hardResetsMax:
                                    sendReboot(options.tegraIP, sutDataPort)
                    else:
                        eventQueue.put(('start',))
            elif state == 'stop' or state == 'offline':
                stopSlave(pidFile)
                bbActive = False
            elif state == 'start':
                if tegraActive and not bbActive:
                    log.debug('starting buildslave in %s' % options.bbpath)
                    bbProc, foo = runCommand(['twistd', '--no_save',
                                                        '--rundir=%s' % options.bbpath,
                                                        '--pidfile=%s' % pidFile,
                                                        '--python=%s' % os.path.join(options.bbpath, 'buildbot.tac')], env=bbEnv)
                    bbActive = False
                    if bbProc is not None:
                        log.info('buildslave start returned %d' % bbProc.returncode)
                        if bbProc.returncode == 0 or bbProc.returncode == 1:
                            bbActive = True
            elif state == 'dialback':
                softCount  = 0
                softResets = 0
            elif state == 'terminate':
                break

        log.debug('bbActive %s tegraActive %s' % (bbActive, tegraActive))

        if os.path.isfile(errorFile):
            if bbActive:
                log.error('errorFile detected - sending stop request')
                eventQueue.put(('stop',))

        if bbActive:
            if os.path.isfile(pidFile):
                n = time.time()
                if int(n - lastHangCheck) > 300:
                    lastHangCheck = n
                    if not checkSlave(options.bbpath, options.hangtime):
                        eventQueue.put(('offline',))
            else:
                log.error('buildbot should be active but pidfile not found, marking as offline')
                eventQueue.put(('offline',))
        else:
            if os.path.isfile(pidFile):
                log.error('buildbot should NOT be active but pidfile found, killing buildbot')
                eventQueue.put(('stop',))

    if bbActive:
        stopSlave(pidFile)

    log.info('monitor stopped')

def handleSigTERM(signum, frame):
    if pidFile is not None:
        try:
            eventQueue.put(('terminate',))
            os.remove(pidFile)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass
    sys.exit(0)



if __name__ == '__main__':
    ourIP = getOurIP()

    if ourIP is None:
        log.error('our IP address is not defined, exiting')
        sys.exit(1)

    loadOptions()

    p = os.getpid()
    log.info('%s: ourIP %s tegra %s tegraIP %s bbpath %s' % (p, ourIP, options.tegra, options.tegraIP, options.bbpath))

    pidFile = os.path.join(ourPath, '%s.pid' % ourName)

    signal.signal(signal.SIGTERM, handleSigTERM)

    if options.background and not 'stop' in options.args:
        daemon = Daemon(pidFile)
        daemon.start()

    db = Process(name='dialback',    target=handleDialback, args=(sutDialbackPort, eventQueue))
    mt = Process(name=options.tegra, target=monitorTegra,   args=(eventQueue,))

    db.start()
    mt.start()

    monitorEvents()

    # killPID(db.pid)
    # killPID(mt.pid)
    # 
    # db.join()
    # mt.join()

