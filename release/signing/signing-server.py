#!/usr/bin/python
"""
signing-server [options] server.ini
"""
import os
import hashlib, hmac
from subprocess import Popen, STDOUT, PIPE
import re
import tempfile
import shutil
import shlex
import signal
import time
import binascii

import logging

from signing import sha1sum, safe_unlink

# External dependencies
import gevent
import gevent.queue as queue
from gevent.event import Event
import webob
from IPy import IP

log = logging.getLogger(__name__)

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
    def __init__(self, signcmd, inputdir, outputdir, concurrency, passphrases):
        self.signcmd = signcmd
        self.concurrency = concurrency
        self.inputdir = inputdir
        self.outputdir = outputdir

        self.passphrases = passphrases

        self.workers = []
        self.queue = queue.Queue()

        self.messages = queue.Queue()

    def signfile(self, filehash, filename, format_):
        item = (filehash, filename, format_)
        log.debug("Putting %s on the queue", item)
        self.queue.put(item)
        self._start_worker()
        log.debug("%i workers active", len(self.workers))

    def _start_worker(self):
        if len(self.workers) < self.concurrency:
            t = gevent.spawn(self._worker)
            t.link(self._worker_done)
            self.workers.append(t)

    def _worker_done(self, t):
        log.debug("Done worker")
        self.workers.remove(t)
        # If there's still work to do, start another worker
        if self.queue.qsize():
            self._start_worker()
        log.debug("%i workers left", len(self.workers))

    def _stop_pool(self):
        # Kill off all our workers
        for t in self.workers:
            t.kill(block=True, timeout=1)

        self.workers = []
        self.queue = queue.Queue()

    def _worker(self):
        # Main worker process
        # We pop items off the queue and process them

        # How many jobs to process before exiting
        max_jobs = 10
        jobs = 0
        while True:
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

                filehash, filename, format_ = item
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
                    self.messages.put( ('errors', item, 'signing script returned non-zero') )
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
                self.messages.put( ('done', item, outputhash) )
            except:
                # Inconceivable! Something went wrong!
                # Remove our output, it might be corrupted
                safe_unlink(outputfile)
                if os.path.exists(logfile):
                    logoutput = open(logfile).read()
                else:
                    logoutput = None
                log.exception("Exception signing file %s; output: %s ", item, logoutput)
                self.messages.put( ('errors', item, 'worker hit an exception while signing') )
        log.debug("Worker exiting")

class SigningServer:
    def __init__(self, config, formats, passphrases):
        self.signer = Signer(
                config.get('signing', 'signscript'),
                config.get('paths', 'unsigned_dir'),
                config.get('paths', 'signed_dir'),
                config.getint('signing', 'concurrency'),
                passphrases)

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

        self.token_secret = config.get('security', 'token_secret')
        # mapping of token keys to token data
        self.tokens = {}

        # mapping of nonces for token keys
        self.nonces = {}

        self.redis = None
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

        self.redis_prefix = "signing"

        self.signed_dir = config.get('paths', 'signed_dir')
        self.unsigned_dir = config.get('paths', 'unsigned_dir')
        self.allowed_ips = [IP(i) for i in \
                config.get('security', 'allowed_ips').split(',')]
        self.new_token_allowed_ips = [IP(i) for i in \
                config.get('security', 'new_token_allowed_ips').split(',')]
        self.allowed_filenames = [re.compile(e) for e in \
                config.get('security', 'allowed_filenames').split(',')]
        self.min_filesize = config.getint('security', 'min_filesize')
        self.formats = formats
        self.max_token_age = config.getint('security', 'max_token_age')

        for d in self.signed_dir, self.unsigned_dir:
            if not os.path.exists(d):
                log.info("Creating %s directory", d)
                os.makedirs(d)

        self.max_file_age = config.getint('server', 'max_file_age')
        self.token_auth = config.get('security', 'new_token_auth')
        self.cleanup()
        # Start our message handling loop
        gevent.spawn(self.process_messages)

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
        if not 0 < duration < self.max_token_age:
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
        self.pending[(filehash, format_)] = Event()
        self.signer.signfile(filehash, filename, format_)

    def process_messages(self):
        while True:
            msg = self.signer.messages.get()
            log.debug("Got message: %s", msg)
            try:
                if msg[0] == 'errors':
                    item, txt = msg[1:]
                    filehash, filename, format_ = item
                    self.pending[filehash, format_].set()
                    del self.pending[filehash, format_]
                elif msg[0] == 'done':
                    item, outputhash = msg[1:]
                    filehash, filename, format_ = item
                    self.pending[filehash, format_].set()
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

def run(config, formats, passphrases):
    from gevent import pywsgi
    import gevent
    app = SigningServer(config, formats, passphrases)
    class logger(object):
        def write(self, msg):
            log.info(msg)

    server = pywsgi.WSGIServer(
            (config.get('server', 'listen'), config.getint('server', 'port')),
            app,
            certfile=config.get('security', 'public_ssl_cert'),
            keyfile=config.get('security', 'private_ssl_cert'),
            log=logger(),
            )

    cleanup_interval = config.getint('server', 'cleanup_interval')
    def cleanuploop(app):
        try:
            app.cleanup()
        except:
            log.exception("Error cleaning up")
        gevent.spawn_later(cleanup_interval, cleanuploop, app)

    gevent.spawn_later(cleanup_interval, cleanuploop, app)
    server.serve_forever()

if __name__ == '__main__':
    from optparse import OptionParser
    from ConfigParser import RawConfigParser
    import getpass
    import logging.handlers

    parser = OptionParser(__doc__)
    parser.set_defaults(
            loglevel=logging.INFO,
            logfile=None,
            )
    parser.add_option("-v", dest="loglevel", action="store_const",
            const=logging.DEBUG, help="be verbose")
    parser.add_option("-q", dest="loglevel", action="store_const",
            const=logging.WARNING, help="be quiet")
    parser.add_option("-l", dest="logfile", help="log to this file instead of stderr")

    options, args = parser.parse_args()

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

    if len(args) != 1:
        parser.error("Need just one server.ini file to read")

    config = RawConfigParser()
    if config.read(args) != args:
        parser.error("Error reading config file: %s" % args[0])

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

    try:
        run(config, formats, passphrases)
    except:
        log.exception("error running server")
        raise
    finally:
        log.info("exiting")
