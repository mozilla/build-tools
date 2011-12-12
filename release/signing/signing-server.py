#!/usr/bin/python
"""
signing-server [options] server.ini
"""
import os, site
# Modify our search path to find our modules
site.addsitedir(os.path.join(os.path.dirname(__file__), "../../lib/python"))
import hashlib, hmac
from subprocess import Popen, STDOUT, PIPE
import re
import tempfile
import shutil
import shlex
import signal
import time
import binascii
import multiprocessing
import socket

import logging
import logging.handlers

from signing import sha1sum as sync_sha1sum, safe_unlink

# External dependencies
import daemon
import webob
from IPy import IP

import gevent.queue as queue
import gevent.backdoor
from gevent.event import Event
from gevent import pywsgi

log = logging.getLogger(__name__)

# We need to ignore SIGINT (KeyboardInterrupt) in the children so that the
# parent exits properly.
def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

_sha1sum_worker_pool = None
def sha1sum(fn):
    "Non-blocking sha1sum. Will calculate sha1sum of fn in a subprocess"
    result = _sha1sum_worker_pool.apply_async(sync_sha1sum, args=(fn,))
    # Most of the time we'll complete pretty fast, so don't need to sleep very
    # long
    sleep_time = 0.1
    while not result.ready():
        gevent.sleep(sleep_time)
        # Increase the time we sleep next time, up to a maximum of 5 seconds
        sleep_time = min(5, sleep_time*2)
    return result.get()

def sha1string(s):
    "Return the sha1 hash of the string s"
    return hashlib.sha1(s).digest()

def b64(s):
    "Return s base64 encoded, with tailing whitespace and = removed"
    return binascii.b2a_base64(s).rstrip("=\n")

def b64sha1sum(s):
    return b64(sha1string(s))

def make_token_data(slave_ip, valid_from, valid_to, chaff_bytes=16):
    """Return a string suitable for using as token data. This string will
    be signed, and the signature passed back to clients as the token
    key."""
    chaff = b64(os.urandom(chaff_bytes))
    block = "%s:%s:%s:%s" % (slave_ip, valid_from, valid_to,
            chaff)
    return block

def sign_data(data, secret, hsh=hashlib.sha256):
    """Returns b64(hmac(secret, data))"""
    h = hmac.new(secret, data, hsh)
    return b64(h.digest())

def verify_token(token_data, token, secret):
    """Returns True if token is the proper signature for
    token_data."""
    return sign_data(token_data, secret) == token

def unpack_token_data(token_data):
    """Reverse of make_token_data: takes an encoded string and returns a
    dictionary with token parameters as keys."""
    bits = token_data.split(":")
    return dict(
            slave_ip=bits[0],
            valid_from=int(bits[1]),
            valid_to=int(bits[2]),
            )

def safe_copyfile(src, dest):
    """safely copy src to dest using a temporary intermediate and then renaming
    to dest"""
    fd, tmpname = tempfile.mkstemp(dir=os.path.dirname(dest))
    shutil.copyfileobj(open(src, 'rb'), os.fdopen(fd, 'wb'))
    shutil.copystat(src, tmpname)
    os.rename(tmpname, dest)

def run_signscript(cmd, inputfile, outputfile, filename, format_, passphrase=None, max_tries=5):
    """Run the signing script `cmd`, passing the inputfile, outputfile,
    original filename and format.

    If passphrase is set, it is passed on standard input.

    Returns 0 on success, non-zero otherwise.

    The command currently is allowed 10 seconds to complete before being killed
    and tried again.
    """
    if isinstance(cmd, basestring):
        cmd = shlex.split(cmd)
    else:
        cmd = cmd[:]

    cmd.extend((format_, inputfile, outputfile, filename))
    output = open(outputfile + '.out', 'wb')
    max_time = 10
    tries = 0
    while True:
        start = time.time()
        proc = Popen(cmd, stdout=output, stderr=STDOUT, stdin=PIPE, close_fds=True)
        if passphrase:
            proc.stdin.write(passphrase)
        proc.stdin.close()
        log.debug("%s: %s", proc.pid, cmd)
        siglist = [signal.SIGINT, signal.SIGTERM]
        while True:
            if time.time() - start > max_time:
                log.debug("%s: Exceeded timeout", proc.pid)
                # Kill off the process
                if siglist:
                    sig = siglist.pop(0)
                else:
                    sig = signal.SIGKILL
                try:
                    os.kill(proc.pid, sig)
                    gevent.sleep(1)
                    os.kill(proc.pid, 0)
                except OSError:
                    # The process is gone now
                    rc = -1
                    break

            rc = proc.poll()
            if rc is not None:
                break

            # Check again in a bit
            gevent.sleep(0.25)

        if rc == 0:
            log.debug("%s: Success!", proc.pid)
            return 0
        # Try again it a bit
        log.info("%s: run_signscript: Failed with rc %i; retrying in a bit", proc.pid, rc)
        tries += 1
        if tries >= max_tries:
            log.warning("run_signscript: Exceeded maximum number of retries; exiting")
            return 1
        gevent.sleep(5)

class Signer(object):
    """
    Main signing object

    `signcmd` is a string representing which command to run to sign files
    `inputdir` and `outputdir` are where uploaded files and signed files will be stored
    `passphrases` is a dict of format => passphrase
    `concurrency` is how many workers to run
    """
    stopped = False
    def __init__(self, app, signcmd, inputdir, outputdir, concurrency, passphrases):
        self.app = app
        self.signcmd = signcmd
        self.concurrency = concurrency
        self.inputdir = inputdir
        self.outputdir = outputdir

        self.passphrases = passphrases

        self.workers = []
        self.queue = queue.Queue()

    def signfile(self, filehash, filename, format_):
        assert not self.stopped
        e = Event()
        item = (filehash, filename, format_, e)
        log.debug("Putting %s on the queue", item)
        self.queue.put(item)
        self._start_worker()
        log.debug("%i workers active", len(self.workers))
        return e

    def _start_worker(self):
        if len(self.workers) < self.concurrency:
            t = gevent.spawn(self._worker)
            t.link(self._worker_done)
            self.workers.append(t)

    def _worker_done(self, t):
        log.debug("Done worker")
        self.workers.remove(t)
        # If there's still work to do, start another worker
        if self.queue.qsize() and not self.stopped:
            self._start_worker()
        log.debug("%i workers left", len(self.workers))

    def _worker(self):
        # Main worker process
        # We pop items off the queue and process them

        # How many jobs to process before exiting
        max_jobs = 10
        jobs = 0
        while True:
            # Event to signal when we're done
            e = None
            try:
                jobs += 1
                # Fall on our sword if we're too old
                if jobs >= max_jobs:
                    break

                try:
                    item = self.queue.get(block=False)
                    if not item:
                        break
                except queue.Empty:
                    log.debug("no items, exiting")
                    break

                filehash, filename, format_, e = item
                log.info("Signing %s (%s - %s)", filename, format_, filehash)

                inputfile = os.path.join(self.inputdir, filehash)
                outputfile = os.path.join(self.outputdir, format_, filehash)
                logfile = outputfile + ".out"

                if not os.path.exists(os.path.join(self.outputdir, format_)):
                    os.makedirs(os.path.join(self.outputdir, format_))

                retval = run_signscript(self.signcmd, inputfile, outputfile,
                        filename, format_, self.passphrases.get(format_))

                if retval != 0:
                    if os.path.exists(logfile):
                        logoutput = open(logfile).read()
                    else:
                        logoutput = None
                    log.warning("Signing failed %s (%s - %s)", filename, format_, filehash)
                    log.warning("Signing log: %s", logoutput)
                    safe_unlink(outputfile)
                    self.app.messages.put( ('errors', item, 'signing script returned non-zero') )
                    continue

                # Copy our signed result into unsigned and signed so if
                # somebody wants to get this file signed again, they get the
                # same results.
                outputhash = sha1sum(outputfile)
                log.debug("Copying result to %s", outputhash)
                copied_input = os.path.join(self.inputdir, outputhash)
                if not os.path.exists(copied_input):
                    safe_copyfile(outputfile, copied_input)
                copied_output = os.path.join(self.outputdir, format_, outputhash)
                if not os.path.exists(copied_output):
                    safe_copyfile(outputfile, copied_output)
                self.app.messages.put( ('done', item, outputhash) )
            except:
                # Inconceivable! Something went wrong!
                # Remove our output, it might be corrupted
                safe_unlink(outputfile)
                if os.path.exists(logfile):
                    logoutput = open(logfile).read()
                else:
                    logoutput = None
                log.exception("Exception signing file %s; output: %s ", item, logoutput)
                self.app.messages.put( ('errors', item, 'worker hit an exception while signing') )
            finally:
                if e:
                    e.set()
        log.debug("Worker exiting")

class SigningServer:
    signer = None
    def __init__(self, config, passphrases):
        self.passphrases = passphrases
        ##
        # Stats
        ##
        # How many successful GETs have we had?
        self.hits = 0
        # How many unsuccesful GETs have we had? (not counting pending jobs)
        self.misses = 0
        # How many uploads have we had?
        self.uploads = 0

        # Mapping of file hashes to gevent Events
        self.pending = {}

        # mapping of token keys to token data
        self.tokens = {}

        # mapping of nonces for token keys
        self.nonces = {}

        self.redis = None
        self.redis_prefix = "signing"

        self.load_config(config)

        self.messages = queue.Queue()

        # Start our message handling loop
        gevent.spawn(self.process_messages)

        # Start our cleanup loop
        gevent.spawn(self.cleanup_loop)

    def load_config(self, config):
        self.token_secret = config.get('security', 'token_secret')
        if config.has_option('server', 'redis'):
            import redis
            host = config.get('server', 'redis')
            log.info("Connecting to redis server %s", host)
            if ':' in host:
                host, port = host.split(":")
                port = int(port)
                self.redis = redis.Redis(host=host, port=port)
            else:
                self.redis = redis.Redis(host=host)

        self.signed_dir = config.get('paths', 'signed_dir')
        self.unsigned_dir = config.get('paths', 'unsigned_dir')
        self.allowed_ips = [IP(i) for i in \
                config.get('security', 'allowed_ips').split(',')]
        self.new_token_allowed_ips = [IP(i) for i in \
                config.get('security', 'new_token_allowed_ips').split(',')]
        self.allowed_filenames = [re.compile(e) for e in \
                config.get('security', 'allowed_filenames').split(',')]
        self.min_filesize = config.getint('security', 'min_filesize')
        self.formats = [f.strip() for f in config.get('signing', 'formats').split(',')]
        self.max_token_age = config.getint('security', 'max_token_age')
        self.max_file_age = config.getint('server', 'max_file_age')
        self.token_auth = config.get('security', 'new_token_auth')
        self.cleanup_interval = config.getint('server', 'cleanup_interval')

        for d in self.signed_dir, self.unsigned_dir:
            if not os.path.exists(d):
                log.info("Creating %s directory", d)
                os.makedirs(d)

        self.signer = Signer(self,
                config.get('signing', 'signscript'),
                config.get('paths', 'unsigned_dir'),
                config.get('paths', 'signed_dir'),
                config.getint('signing', 'concurrency'),
                self.passphrases)

    def verify_nonce(self, token, nonce):
        if self.redis:
            next_nonce_digest = self.redis.get(
                    "%s:nonce:%s" % (self.redis_prefix, b64sha1sum(token)))
        else:
            next_nonce_digest = self.nonces.get(token)

        if next_nonce_digest is None:
            return False

        if sign_data(nonce, self.token_secret) != next_nonce_digest:
            return False

        # Generate the next one
        valid_to = unpack_token_data(self.tokens[token])['valid_to']
        next_nonce = b64(os.urandom(16))
        self.save_nonce(token, next_nonce, valid_to)
        return next_nonce

    def save_nonce(self, token, nonce, expiry):
        nonce_digest = sign_data(nonce, self.token_secret)
        self.nonces[token] = nonce_digest
        if self.redis:
            self.redis.setex("%s:nonce:%s" %
                    (self.redis_prefix, b64sha1sum(token)),
                    nonce_digest,
                    int(expiry-time.time()),
                    )

    def verify_token(self, token, slave_ip):
        token_data = self.tokens.get(token)
        if not token_data:
            if not self.redis:
                log.info("unknown token %s", token)
                log.debug("Tokens: %s", self.tokens)
                return False

            log.info("couldn't find token data for key %s locally, checking cache", token)
            token_data = self.redis.get("%s:tokens:%s" % (self.redis_prefix, b64sha1sum(token)))
            if not token_data:
                log.info("not in cache; failing verify_token")
                return False
            # Save it for later
            self.tokens[token] = token_data

        info = unpack_token_data(token_data)
        valid_from, valid_to = info['valid_from'], info['valid_to']
        now = time.time()
        if now < valid_from or now > valid_to:
            log.info("Invalid time window; deleting key")
            self.delete_token(token)
            return False

        if info['slave_ip'] != slave_ip:
            log.info("Invalid slave ip")
            self.delete_token(token)
            return False

        return verify_token(token_data, token, self.token_secret)

    def delete_token(self, token):
        if token in self.tokens:
            del self.tokens[token]
        if token in self.nonces:
            del self.nonces[token]
        if self.redis:
            self.redis.delete("%s:tokens:%s" % (self.redis_prefix, b64sha1sum(token)))
            self.redis.delete("%s:nonce:%s" % (self.redis_prefix, b64sha1sum(token)))

    def save_token(self, token, token_data):
        self.tokens[token] = token_data
        valid_to = unpack_token_data(token_data)['valid_to']
        if self.redis:
            self.redis.setex("%s:tokens:%s" %
                    (self.redis_prefix, b64sha1sum(token)),
                    token_data,
                    int(valid_to-time.time()),
                    )

        # Set the initial nonce to ""
        self.save_nonce(token, "", valid_to)

    def get_token(self, slave_ip, duration):
        duration = int(duration)
        if not 0 < duration <= self.max_token_age:
            log.debug("invalid duration")
            raise ValueError("Invalid duration: %s", duration)
        now = int(time.time())
        valid_from = now
        valid_to = now + duration
        log.info("request for token for slave %s for %i seconds", slave_ip, duration)
        data = make_token_data(slave_ip, valid_from, valid_to)
        token = sign_data(data, self.token_secret)
        self.save_token(token, data)
        log.debug("Tokens: %s", self.tokens)
        return token

    def cleanup_loop(self):
        try:
            self.cleanup()
        except:
            log.exception("Error cleaning up")
        finally:
            gevent.spawn_later(
                self.cleanup_interval,
                self.cleanup_loop,
                )

    def cleanup(self):
        log.info("Stats: %i hits; %i misses; %i uploads", self.hits, self.misses, self.uploads)
        log.debug("Pending: %s", self.pending)
        # Find files in unsigned that have bad hashes and delete them
        log.debug("Cleaning up...")
        now = time.time()
        for f in os.listdir(self.unsigned_dir):
            unsigned = os.path.join(self.unsigned_dir, f)
            if not f.endswith(".fn") and sha1sum(unsigned) != f:
                log.info("Deleting %s with bad hash", unsigned)
                safe_unlink(unsigned)
                continue

            # Clean up old files
            if os.path.getmtime(unsigned) < now-self.max_file_age:
                log.info("Deleting %s (too old)", unsigned)
                safe_unlink(unsigned)
                continue

        # Find files in signed that don't have corresponding files in unsigned
        # and delete them
        for format_ in os.listdir(self.signed_dir):
            for f in os.listdir(os.path.join(self.signed_dir, format_)):
                signed = os.path.join(self.signed_dir, format_, f)
                # Don't delete logs
                if signed.endswith(".out"):
                    continue
                unsigned = os.path.join(self.unsigned_dir, f)
                if not os.path.exists(unsigned):
                    log.info("Deleting %s with no unsigned file", signed)
                    safe_unlink(signed)

        # Clean out self.tokens and self.nonces
        now = time.time()
        for token, token_data in self.tokens.items():
            info = unpack_token_data(token_data)
            if info['valid_to'] < now:
                log.debug("Deleting expired token %s", token)
                self.delete_token(token)

    def submit_file(self, filehash, filename, format_):
        assert (filehash, format_) not in self.pending
        e = self.signer.signfile(filehash, filename, format_)
        self.pending[(filehash, format_)] = e

    def process_messages(self):
        while True:
            msg = self.messages.get()
            log.debug("Got message: %s", msg)
            try:
                if msg[0] == 'errors':
                    item, txt = msg[1:]
                    filehash, filename, format_, e = item
                    del self.pending[filehash, format_]
                elif msg[0] == 'done':
                    item, outputhash = msg[1:]
                    filehash, filename, format_, e = item
                    del self.pending[filehash, format_]
                    # Remember the filename for the output file too
                    self.save_filename(outputhash, filename)
                else:
                    log.error("Unknown message type: %s", msg)
            except:
                log.exception("Error handling message: %s", msg)

    def get_path(self, filename, format_):
        # Return path of filename under signed-files
        return os.path.join(self.signed_dir, format_, os.path.basename(filename))

    def get_filename(self, filehash):
        try:
            filename_fn = os.path.join(self.unsigned_dir, filehash + ".fn")
            os.utime(filename_fn, None)
            return open(filename_fn, 'rb').read()
        except OSError:
            return None

    def save_filename(self, filehash, filename):
        filename_fn = os.path.join(self.unsigned_dir, filehash + ".fn")
        fd, tmpname = tempfile.mkstemp(dir=self.unsigned_dir)
        fp = os.fdopen(fd, 'wb')
        fp.write(filename)
        fp.close()
        os.rename(tmpname, filename_fn)

    def __call__(self, environ, start_response):
        """WSGI entry point."""

        # Validate the client's IP
        remote_addr = environ['REMOTE_ADDR']
        if not any(remote_addr in net for net in self.allowed_ips):
            log.info("%(REMOTE_ADDR)s forbidden based on IP address" % environ)
            start_response("403 Forbidden", [])
            return ""

        method = getattr(self, 'do_%s' % environ['REQUEST_METHOD'], None)
        if not method:
            start_response("405 Method Not Allowed", [])
            return ""

        log.info("%(REMOTE_ADDR)s %(REQUEST_METHOD)s %(PATH_INFO)s" % environ)
        return method(environ, start_response)

    def do_GET(self, environ, start_response):
        """
        GET /sign/<format>/<hash>
        """
        try:
            _, magic, format_, filehash = environ['PATH_INFO'].split('/')
            assert magic == 'sign'
            assert format_ in self.formats
        except:
            log.debug("bad request: %s", environ['PATH_INFO'])
            start_response("400 Bad Request", [])
            yield ""
            return

        filehash = os.path.basename(environ['PATH_INFO'])
        try:
            pending = self.pending.get((filehash, format_))
            if pending:
                log.debug("Waiting for pending job")
                # Wait up to a minute for this to finish
                pending.wait(timeout=60)
                log.debug("Pending job finished!")
            fn = self.get_path(filehash, format_)
            filename = self.get_filename(filehash)
            if filename:
                log.debug("Looking for %s (%s)", fn, filename)
            else:
                log.debug("Looking for %s", fn)
            checksum = sha1sum(fn)
            headers = [
                    ('X-SHA1-Digest', checksum),
                    ('Content-Length', os.path.getsize(fn)),
                        ]
            fp = open(fn, 'rb')
            os.utime(fn, None)
            log.debug("%s is OK", fn)
            start_response("200 OK", headers)
            while True:
                data = fp.read(1024**2)
                if not data:
                    break
                yield data
            self.hits += 1
        except IOError:
            log.debug("%s is missing", fn)
            headers = []
            fn = os.path.join(self.unsigned_dir, filehash)
            if (filehash, format_) in self.pending:
                log.info("File is pending, come back soon!")
                log.debug("Pending: %s", self.pending)
                headers.append( ('X-Pending', 'True') )

            # Maybe we have the file, but not for this format
            # If so, queue it up and return a pending response
            # This prevents the client from having to upload the file again
            elif os.path.exists(fn):
                log.debug("GET for file we already have, but not for the right format")
                # Validate the file
                myhash = sha1sum(fn)
                if myhash != filehash:
                    log.warning("%s is corrupt; deleting (%s != %s)", fn, filehash, myhash)
                    safe_unlink(fn)
                else:
                    filename = self.get_filename(filehash)
                    if filename:
                        self.submit_file(filehash, filename, format_)
                        log.info("File is pending, come back soon!")
                        headers.append( ('X-Pending', 'True') )
                    else:
                        log.debug("I don't remember the filename; re-submit please!")
            else:
                self.misses += 1

            start_response("404 Not Found", headers)
            yield ""

    def handle_upload(self, environ, start_response, values, rest, next_nonce):
        format_ = rest[0]
        assert format_ in self.formats
        filehash = values['sha1']
        filename = values['filename']
        log.info("Request to %s sign %s (%s) from %s", format_, filename, filehash, environ['REMOTE_ADDR'])
        fn = os.path.join(self.unsigned_dir, filehash)
        headers = [('X-Nonce', next_nonce)]
        if os.path.exists(fn):
            # Validate the file
            mydigest = sha1sum(fn)

            if mydigest != filehash:
                log.warning("%s is corrupt; deleting (%s != %s)", fn, mydigest, filehash)
                safe_unlink(fn)

            elif os.path.exists(os.path.join(self.signed_dir, filehash)):
                # Everything looks ok
                log.info("File already exists")
                start_response("202 File already exists", headers)
                return ""

            elif (filehash, format_) in self.pending:
                log.info("File is pending")
                start_response("202 File is pending", headers)
                return ""

            log.info("Not pending or already signed, re-queue")

        # Validate filename
        if not any(exp.match(filename) for exp in self.allowed_filenames):
            log.info("%s forbidden due to invalid filename: %s", environ['REMOTE_ADDR'], filename)
            start_response("403 Unacceptable filename", headers)
            return ""

        try:
            fd, tmpname = tempfile.mkstemp(dir=self.unsigned_dir)
            fp = os.fdopen(fd, 'wb')

            h = hashlib.new('sha1')
            s = 0
            while True:
                data = values['filedata'].file.read(1024**2)
                if not data:
                    break
                s += len(data)
                h.update(data)
                fp.write(data)
            fp.close()
        except:
            log.exception("Error downloading data")
            os.unlink(tmpname)

        if s < self.min_filesize:
            os.unlink(tmpname)
            start_response("400 File too small", headers)
            return ""

        if h.hexdigest() != filehash:
            os.unlink(tmpname)
            log.warn("Hash mismatch. Bad upload?")
            start_response("400 Hash mismatch", headers)
            return ""

        # Good to go!  Rename the temporary filename to the real filename
        self.save_filename(filehash, filename)
        os.rename(tmpname, fn)
        self.submit_file(filehash, filename, format_)
        start_response("202 Accepted", headers)
        self.uploads += 1
        return ""

    def handle_token(self, environ, start_response, values):
        if 'expire' in values:
            self.delete_token(values['expire'])
        else:
            token = self.get_token(
                    values['slave_ip'],
                    values['duration'],
                    )
        start_response("200 OK", [])
        return token

    def do_POST(self, environ, start_response):
        req = webob.Request(environ)
        values = req.POST
        headers = []

        try:
            path_bits = environ['PATH_INFO'].split('/')
            magic = path_bits[1]
            rest = path_bits[2:]
            if not magic in ('sign', 'token'):
                log.exception("bad request: %s", environ['PATH_INFO'])
                start_response("400 Bad Request", [])
                return ""

            if magic == 'token':
                remote_addr = environ['REMOTE_ADDR']
                if not any(remote_addr in net for net in self.new_token_allowed_ips):
                    log.info("%(REMOTE_ADDR)s forbidden based on IP address" % environ)
                    start_response("403 Forbidden", [])
                    return ""
                try:
                    basic, auth = req.headers['Authorization'].split()
                    if basic != "Basic" or auth.decode("base64") != self.token_auth:
                        start_response("401 Authorization Required", [])
                        return ""
                except:
                    start_response("401 Authorization Required", [])
                    return ""

                return self.handle_token(environ, start_response, values)
            elif magic == 'sign':
                # Validate token
                if 'token' not in values:
                    start_response("400 Missing token", [])
                    return ""

                slave_ip = environ['REMOTE_ADDR']
                if not self.verify_token(values['token'], slave_ip):
                    start_response("400 Invalid token", [])
                    return ""

                # Validate nonce
                if 'nonce' not in values:
                    self.delete_token(values['token'])
                    start_response("400 Missing nonce", [])
                    return ""

                next_nonce = self.verify_nonce(values['token'], values['nonce'])
                if not next_nonce:
                    self.delete_token(values['token'])
                    start_response("400 Invalid nonce", [])
                    return ""

                headers.append( ('X-Nonce', next_nonce) )

                return self.handle_upload(environ, start_response, values, rest, next_nonce)
        except:
            log.exception("ISE")
            start_response("500 Internal Server Error", headers)
            return ""

def load_config(filename):
    config = RawConfigParser()
    if config.read([filename]) != [filename]:
        return None
    return config

def create_server(app, listener, config):
    # Simple wrapper so pywsgi uses logging to log instead of writing to stderr
    class logger(object):
        def write(self, msg):
            log.info(msg)

    server = pywsgi.WSGIServer(
            listener,
            app,
            certfile=config.get('security', 'public_ssl_cert'),
            keyfile=config.get('security', 'private_ssl_cert'),
            log=logger(),
            )
    return server

def run(config_filename, passphrases):
    log.info("Running with pid %i", os.getpid())

    # Start our worker pool now, before we create our sockets for the web app
    # otherwise the workers inherit the file descriptors for the http(s)
    # socket and we have problems shutting down cleanly
    global _sha1sum_worker_pool
    if not _sha1sum_worker_pool:
        _sha1sum_worker_pool = multiprocessing.Pool(None, init_worker)
    app = None
    listener = None
    server = None
    backdoor = None
    handler = None
    backdoor_state = {}
    while True:
        log.info("Loading configuration")
        config = load_config(config_filename)
        if not app:
            app = SigningServer(config, passphrases)
        else:
            app.load_config(config)

        listen_addr = (config.get('server', 'listen'), config.getint('server', 'port'))
        if not listener or listen_addr != listener.getsockname():
            if listener and server:
                log.info("Listening address has changed, stopping old wsgi server")
                log.debug("Old address: %s", listener.getsockname())
                log.debug("New address: %s", listen_addr)
                server.stop()
            listener = gevent.socket.socket()
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(listen_addr)
            listener.listen(256)

        server = create_server(app, listener, config)

        backdoor_state['server'] = server
        backdoor_state['app'] = app

        if config.has_option('server', 'backdoor_port'):
            backdoor_port = config.getint('server', 'backdoor_port')
            if not backdoor or backdoor.server_port != backdoor_port:
                if backdoor:
                    log.info("Stopping old backdoor on port %i", backdoor.server_port)
                    backdoor.stop()
                log.info("Starting backdoor on port %i", backdoor_port)
                backdoor = gevent.backdoor.BackdoorServer(
                        ('127.0.0.1', backdoor_port),
                        locals=backdoor_state)
                gevent.spawn(backdoor.serve_forever)

        # Handle SIGHUP
        # Create an event to wait on
        # Our SIGHUP handler will set the event, allowing us to continue
        sighup_event = Event()
        h = gevent.signal(signal.SIGHUP, lambda e: e.set(), sighup_event)
        if handler:
            # Cancel our old handler
            handler.cancel()
        handler = h
        log.info("Serving on %s", repr(server))
        try:
            gevent.spawn(server.serve_forever)
            # Wait for SIGHUP
            sighup_event.wait()
        except KeyboardInterrupt:
            break
    log.info("pid %i exiting normally", os.getpid())

def setup_logging(options):
    if options.logfile:
        handler = logging.handlers.RotatingFileHandler(options.logfile,
                maxBytes=1024**2, backupCount=10)
    else:
        handler = logging.StreamHandler()

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(options.loglevel)

if __name__ == '__main__':
    from optparse import OptionParser
    from ConfigParser import RawConfigParser
    import getpass
    import sys

    parser = OptionParser(__doc__)
    parser.set_defaults(
            loglevel=logging.INFO,
            logfile=None,
            daemonize=False,
            pidfile="signing.pid",
            action="run",
            )
    parser.add_option("-v", dest="loglevel", action="store_const",
            const=logging.DEBUG, help="be verbose")
    parser.add_option("-q", dest="loglevel", action="store_const",
            const=logging.WARNING, help="be quiet")
    parser.add_option("-l", dest="logfile", help="log to this file instead of stderr")
    parser.add_option("-d", dest="daemonize", action="store_true",
            help="daemonize process")
    parser.add_option("--pidfile", dest="pidfile")
    parser.add_option("--stop", dest="action", action="store_const", const="stop")
    parser.add_option("--reload", dest="action", action="store_const", const="reload")
    parser.add_option("--restart", dest="action", action="store_const", const="restart")

    options, args = parser.parse_args()

    if options.action == "stop":
        try:
            pid = int(open(options.pidfile).read())
            os.kill(pid, signal.SIGINT)
        except (IOError,ValueError):
            log.info("no pidfile, assuming process is stopped")
        sys.exit(0)
    elif options.action == "reload":
        pid = int(open(options.pidfile).read())
        os.kill(pid, signal.SIGHUP)
        sys.exit(0)

    if len(args) != 1:
        parser.error("Need just one server.ini file to read")

    config = load_config(args[0])
    if not config:
        parser.error("Error reading config file: %s" % args[0])

    setup_logging(options)

    # Read passphrases
    passphrases = {}
    formats = [f.strip() for f in config.get('signing', 'formats').split(',')]
    for format_ in formats:
        passphrase = getpass.getpass("%s passphrase: " % format_)
        if not passphrase:
            passphrase = None
        try:
            log.info("checking %s passphrase", format_)
            src = config.get('signing', 'testfile_%s' % format_)
            tmpdir = tempfile.mkdtemp()
            dst = os.path.join(tmpdir, os.path.basename(src))
            shutil.copyfile(src, dst)
            if 0 != run_signscript(config.get('signing', 'signscript'), src, dst, src, format_, passphrase, max_tries=2):
                log.error("Bad passphrase: %s", open(dst + ".out").read())
                assert False
            log.info("%s passphrase OK", format_)
            passphrases[format_] = passphrase
        finally:
            shutil.rmtree(tmpdir)

    # Possibly stop the old instance
    # We do this here so that we don't have to wait for the user to enter
    # passwords before stopping/starting the new instance.
    if options.action == 'restart':
        try:
            pid = int(open(options.pidfile).read())
            log.info("Killing old server pid:%i", pid)
            os.kill(pid, signal.SIGINT)
            # Wait for it to exit
            while True:
                log.debug("Waiting for pid %i to exit", pid)
                # This will raise OSError once the process exits
                os.kill(pid, 0)
                gevent.sleep(1)
        except (IOError, ValueError):
            log.info("no pidfile, assuming process is stopped")
        except OSError:
            # Process is done
            log.debug("pid %i has exited", pid)

    if options.daemonize:
        curdir = os.path.abspath(os.curdir)
        pidfile = os.path.abspath(options.pidfile)
        logfile = os.path.abspath(options.logfile)

        daemon_ctx = daemon.DaemonContext(
                # We do our own signal handling in run()
                signal_map={},
                working_directory=curdir,
                )
        daemon_ctx.open()

        # gevent needs to be reinitialized after the hardcore forking action
        gevent.reinit()
        open(pidfile, 'w').write(str(os.getpid()))

        # Set up logging again! createDaemon has closed all our open file
        # handles
        setup_logging(options)

    try:
        run(args[0], passphrases)
    except:
        log.exception("error running server")
        raise
    finally:
        try:
            daemon_ctx.close()
            if options.daemonize:
                safe_unlink(pidfile)
            log.info("exiting")
        except:
            log.exception("error shutting down")
