import tempfile, os, hashlib, shutil, bz2, re, sys, time, urllib2, httplib
import fnmatch
import logging
import socket
import shlex
from subprocess import PIPE, Popen, check_call, STDOUT, call

log = logging.getLogger(__name__)

SEVENZIP = os.environ.get('SEVENZIP', '7z')
MAR = os.environ.get('MAR', 'mar')
TAR = os.environ.get('TAR', 'tar')

def _noumask():
    # Utility function to set a umask of 000
    os.umask(0)

def cygpath(filename):
    """Convert a cygwin path into a windows style path"""
    if sys.platform == 'cygwin':
        proc = Popen(['cygpath', '-am', filename], stdout=PIPE)
        return proc.communicate()[0].strip()
    else:
        return filename

def convertPath(srcpath, dstdir):
    """Given `srcpath`, return a corresponding path within `dstdir`"""
    bits = srcpath.split("/")
    bits.pop(0)
    # Strip out leading 'unsigned' from paths like unsigned/update/win32/...
    if bits[0] == 'unsigned':
        bits.pop(0)
    return os.path.join(dstdir, *bits)

def fileInfo(filepath, product):
    """Extract information about a release file.  Returns a dictionary with the
    following keys set:
    'product', 'version', 'locale', 'platform', 'contents', 'format',
    'pathstyle'

    'contents' is one of 'complete', 'installer'
    'format' is one of 'mar' or 'exe'
    'pathstyle' is either 'short' or 'long', and refers to if files are all in
        one directory, with the locale as part of the filename ('short' paths,
        firefox 3.0 style filenames), or if the locale names are part of the
        directory structure, but not the file name itself ('long' paths,
        firefox 3.5+ style filenames)
    """
    try:
        # Mozilla 1.9.0 style (aka 'short') paths
        # e.g. firefox-3.0.12.en-US.win32.complete.mar
        filename = os.path.basename(filepath)
        m = re.match("^(%s)-([0-9.]+)\.([-a-zA-Z]+)\.(win32)\.(complete|installer)\.(mar|exe)$" % product, filename)
        if not m:
            raise ValueError("Could not parse: %s" % filename)
        return {'product': m.group(1),
                'version': m.group(2),
                'locale': m.group(3),
                'platform': m.group(4),
                'contents': m.group(5),
                'format': m.group(6),
                'pathstyle': 'short',
                'leading_path' : '',
               }
    except:
        # Mozilla 1.9.1 and on style (aka 'long') paths
        # e.g. update/win32/en-US/firefox-3.5.1.complete.mar
        #      win32/en-US/Firefox Setup 3.5.1.exe
        ret = {'pathstyle': 'long'}
        if filepath.endswith('.mar'):
            ret['format'] = 'mar'
            m = re.search("update/(win32|linux-i686|linux-x86_64|mac|mac64)/([-a-zA-Z]+)/(%s)-(\d+\.\d+(?:\.\d+)?(?:\w+(?:\d+)?)?)\.(complete)\.mar" % product, filepath)
            if not m:
                raise ValueError("Could not parse: %s" % filepath)
            ret['platform'] = m.group(1)
            ret['locale'] = m.group(2)
            ret['product'] = m.group(3)
            ret['version'] = m.group(4)
            ret['contents'] = m.group(5)
            ret['leading_path'] = ''
        elif filepath.endswith('.exe'):
            ret['format'] = 'exe'
            ret['contents'] = 'installer'
            # EUballot builds use a different enough style of path than others
            # that we can't catch them in the same regexp
            if filepath.find('win32-EUballot') != -1:
                ret['platform'] = 'win32'
                m = re.search("(win32-EUballot/)([-a-zA-Z]+)/((?i)%s) Setup (\d+\.\d+(?:\.\d+)?(?:\w+\d+)?(?:\ \w+\ \d+)?)\.exe" % product, filepath)
                if not m:
                    raise ValueError("Could not parse: %s" % filepath)
                ret['leading_path'] = m.group(1)
                ret['locale'] = m.group(2)
                ret['product'] = m.group(3).lower()
                ret['version'] = m.group(4)
            else:
                m = re.search("(partner-repacks/[-a-zA-Z0-9_]+/|)(win32|mac|linux-i686)/([-a-zA-Z]+)/((?i)%s) Setup (\d+\.\d+(?:\.\d+)?(?:\w+(?:\d+)?)?(?:\ \w+\ \d+)?)\.exe" % product, filepath)
                if not m:
                    raise ValueError("Could not parse: %s" % filepath)
                ret['leading_path'] = m.group(1)
                ret['platform'] = m.group(2)
                ret['locale'] = m.group(3)
                ret['product'] = m.group(4).lower()
                ret['version'] = m.group(5)
        else:
            raise ValueError("Unknown filetype for %s" % filepath)

        return ret

def filterFiles(files, product):
    """ Filter out files that we can't sign. Right now this means that
    anything that isn't a win32 .exe or .mar file gets filtered out"""
    for f in files[:]:
        skip = False
        try:
            info = fileInfo(f, product)
            if info['platform'] != 'win32':
                skip = True
            if info['contents'] not in ('complete', 'installer'):
                skip = True
        except ValueError:
            skip = True

        if skip:
            files.remove(f)
            if 'win32' in f:
                if 'xpi' not in f:
                    log.info("Skipping %s", f)

    return files

def sortFiles(files, product, firstLocale):
    """sort files into a specific ordering using the key function defined
    within"""
    # Utility function for sorting files
    # Makes sure that .mar files follow their corresponding .exe files
    def fileKey(f):
        info = fileInfo(f, product)
        locale = info['locale']
        leading_path = info['leading_path']
        if locale == firstLocale and not leading_path:
            localeVal = 0
        else:
            localeVal = 1
        if info['format'] == 'exe':
            exeVal = 0
        else:
            exeVal = 1
        return (localeVal, leading_path, locale, exeVal, f)

    return sorted(files, key=fileKey)

def copyfile(src, dst, copymode=True):
    """Copy src to dst, preserving permissions and times if copymode is True"""
    shutil.copyfile(src, dst)
    if copymode:
        shutil.copymode(src, dst)
        shutil.copystat(src, dst)

def sha1sum(f):
    """Return the SHA-1 hash of the contents of file `f`, in hex format"""
    h = hashlib.sha1()
    fp = open(f, 'rb')
    while True:
        block = fp.read(512*1024)
        if not block:
            break
        h.update(block)
    return h.hexdigest()

def sums_are_equal(base_package, packages):
    """ Check to make sure that the dictionaries of files:checksums are
    exactly equal across a list of packages """
    success = True
    for signed_file in base_package.keys():
        log.debug("comparing file %s", signed_file)
        if not len([p for p in packages if p[signed_file] ==
            packages[0][signed_file]]) == len(packages):
            log.error("%s differs!", signed_file)
            success = False
    return success

def findfiles(root):
    """Return a list of all the files under `root`"""
    retval = []
    for root, dirs, files in os.walk(root):
        for f in files:
            retval.append(os.path.join(root, f))
    return retval

def finddirs(root):
    """Return a list of all the directories under `root`"""
    retval = []
    for root, dirs, files in os.walk(root):
        for d in dirs:
            retval.append(os.path.join(root, d))
    return retval

def unpackexe(exefile, destdir):
    """Unpack the given exefile into destdir, using 7z"""
    nullfd = open(os.devnull, "w")
    exefile = cygpath(os.path.abspath(exefile))
    try:
        check_call([SEVENZIP, 'x', exefile], cwd=destdir, stdout=nullfd, preexec_fn=_noumask)
    except:
        log.exception("Error unpacking exe %s to %s", exefile, destdir)
        raise
    nullfd.close()

def packexe(exefile, srcdir):
    """Pack the files in srcdir into exefile using 7z.

    Requires that stub files are available in checkouts/stubs"""
    exefile = cygpath(os.path.abspath(exefile))
    appbundle = exefile + ".app.7z"

    # Make sure that appbundle doesn't already exist
    # We don't want to risk appending to an existing file
    if os.path.exists(appbundle):
        raise OSError("%s already exists" % appbundle)
    
    files = os.listdir(srcdir)

    SEVENZIP_ARGS = ['-r', '-t7z', '-mx', '-m0=BCJ2', '-m1=LZMA:d27',
            '-m2=LZMA:d19:mf=bt2', '-m3=LZMA:d19:mf=bt2', '-mb0:1', '-mb0s1:2',
            '-mb0s2:3', '-m1fb=128', '-m1lc=4']

    # First, compress with 7z
    stdout = tempfile.TemporaryFile()
    try:
        check_call([SEVENZIP, 'a'] + SEVENZIP_ARGS + [appbundle] + files,
                cwd=srcdir, stdout=stdout, preexec_fn=_noumask)
    except:
        stdout.seek(0)
        data = stdout.read()
        log.error(data)
        log.exception("Error packing exe %s from %s", exefile, srcdir)
        raise
    stdout.close()

    # Then prepend our stubs onto the compressed 7z data
    o = open(exefile, "wb")
    parts = [
            'checkouts/stubs/7z/7zSD.sfx.compressed',
            'checkouts/stubs/tagfile/app.tag',
            appbundle
            ]
    for part in parts:
        i = open(part)
        while True:
            block = i.read(4096)
            if not block:
                break
            o.write(block)
        i.close()
    o.close()
    os.unlink(appbundle)

def bunzip2(filename):
    """Uncompress `filename` in place"""
    log.debug("Uncompressing %s", filename)
    tmpfile = "%s.tmp" % filename
    os.rename(filename, tmpfile)
    b = bz2.BZ2File(tmpfile)
    f = open(filename, "wb")
    while True:
        block = b.read(512*1024)
        if not block:
            break
        f.write(block)
    f.close()
    b.close()
    shutil.copystat(tmpfile, filename)
    shutil.copymode(tmpfile, filename)
    os.unlink(tmpfile)

def bzip2(filename):
    """Compress `filename` in place"""
    log.debug("Compressing %s", filename)
    tmpfile = "%s.tmp" % filename
    os.rename(filename, tmpfile)
    b = bz2.BZ2File(filename, "w")
    f = open(tmpfile, 'rb')
    while True:
        block = f.read(512*1024)
        if not block:
            break
        b.write(block)
    f.close()
    b.close()
    shutil.copystat(tmpfile, filename)
    shutil.copymode(tmpfile, filename)
    os.unlink(tmpfile)

def unpackmar(marfile, destdir):
    """Unpack marfile into destdir"""
    marfile = cygpath(os.path.abspath(marfile))
    nullfd = open(os.devnull, "w")
    try:
        check_call([MAR, '-x', marfile], cwd=destdir, stdout=nullfd, preexec_fn=_noumask)
    except:
        log.exception("Error unpacking mar file %s to %s", marfile, destdir)
        raise
    nullfd.close()

def packmar(marfile, srcdir):
    """Create marfile from the contents of srcdir"""
    nullfd = open(os.devnull, "w")
    files = [f[len(srcdir)+1:] for f in findfiles(srcdir)]
    marfile = cygpath(os.path.abspath(marfile))
    try:
        check_call([MAR, '-c', marfile] + files, cwd=srcdir, preexec_fn=_noumask)
    except:
        log.exception("Error packing mar file %s from %s", marfile, srcdir)
        raise
    nullfd.close()

def unpacktar(tarfile, destdir):
    """ Unpack given tarball into the specified dir """
    nullfd = open(os.devnull, "w")
    tarfile = cygpath(os.path.abspath(tarfile))
    log.debug("unpack tar %s into %s", tarfile, destdir)
    try:
        check_call([TAR, '-xf', tarfile], cwd=destdir, stdout=nullfd, preexec_fn=_noumask)
    except:
        log.exception("Error unpacking tar file %s to %s", tarfile, destdir)
        raise
    nullfd.close()

def tar_dir(tarfile, srcdir):
    """ Pack a tar file using all the files in the given srcdir """
    files = os.listdir(srcdir)
    packtar(tarfile, files, srcdir)
    
def packtar(tarfile, files, srcdir):
    """ Pack the given files into a tar, setting cwd = srcdir"""
    nullfd = open(os.devnull, "w")
    tarfile = cygpath(os.path.abspath(tarfile))
    log.debug("pack tar %s from folder  %s with files " , tarfile, srcdir)
    log.debug( files)
    try:
        check_call([TAR, '-cf', tarfile] + files, cwd=srcdir, stdout=nullfd, preexec_fn=_noumask)
    except:
        log.exception("Error packing tar file %s to %s", tarfile, srcdir)
        raise
    nullfd.close()


def unpackfile(filename, destdir):
    """Unpack a mar or exe into destdir"""
    if filename.endswith(".mar"):
        return unpackmar(filename, destdir)
    elif filename.endswith(".exe"):
        return unpackexe(filename, destdir)
    elif filename.endswith(".tar"):
        return unpacktar(filename, destdir)
    else:
        raise ValueError("Unknown file type: %s" % filename)

def packfile(filename, srcdir):
    """Package up srcdir into filename, archived with 7z for exes or mar for
    mar files"""
    if filename.endswith(".mar"):
        return packmar(filename, srcdir)
    elif filename.endswith(".exe"):
        return packexe(filename, srcdir)
    elif filename.endswith(".tar"):
        return tar_dir(filename, srcdir)
    else:
        raise ValueError("Unknown file type: %s" % filename)

def shouldSign(filename, platform='win32'):
    """Returns True if filename should be signed."""
    # These should already be signed by Microsoft.
    _dont_sign = [
            'D3DCompiler_42.dll', 'd3dx9_42.dll',
            'D3DCompiler_43.dll', 'd3dx9_43.dll',
            'msvc*.dll',
            ]
    ext = os.path.splitext(filename)[1]
    b = os.path.basename(filename)
    if platform == 'mac':
        if b.endswith('.app'):
            return True
    elif platform in ('win32', 'win64'):
        if ext in ('.dll', '.exe') and not any(fnmatch.fnmatch(b, p) for p in _dont_sign):
            return True
    else:
        #We should never get here.
        log.debug("Invalid Platform: %s", platform)
    return False

def getChkFile(filename):
    _special_files = ['freebl3.dll', 'softokn3.dll', 'nssdbm3.dll']
    b = os.path.basename(filename)
    if b in _special_files:
        d = os.path.dirname(filename)
        f = os.path.splitext(b)[0] + '.chk'
        return os.path.join(d, f)
    return None

def checkTools():
    """Returns True if all of the helper commands ($MAR, $SEVENZIP) are
    runnable.

    Raises a OSError if they can't be found.
    """
    # Check that MAR and SEVENZIP are executable
    null = open(os.devnull, "w")
    try:
        call([MAR, '-h'], stdout=null)
    except OSError:
        raise OSError("mar must be in your $PATH, or set via $MAR")
    try:
        call([SEVENZIP, '-h'], stdout=null)
    except OSError:
        raise OSError("7z must be in your $PATH, or set via $SEVENZIP")

def signfile(filename, keydir, fake=False, passphrase=None):
    """Sign the given file with keys in keydir.

    If passphrase is set, it will be sent as stdin to the process.

    If fake is True, then don't actually sign anything, just sleep for a
    second to simulate signing time."""
    if fake:
        time.sleep(1)
        return
    basename = os.path.basename(filename)
    dirname = os.path.dirname(filename)
    stdout = tempfile.TemporaryFile()
    command = ['signcode',
        '-spc', '%s/MozAuthenticode.spc' % keydir,
        '-v', '%s/MozAuthenticode.pvk' % keydir,
        '-t', 'http://timestamp.verisign.com/scripts/timestamp.dll',
        '-i', 'http://www.mozilla.com',
        '-a', 'sha1',
        # Try 5 times, and wait 60 seconds between tries
        '-tr', '5',
        '-tw', '60',
        basename]
    try:
        proc = Popen(command, cwd=dirname, stdout=stdout, stderr=STDOUT, stdin=PIPE)
        if passphrase:
            proc.stdin.write(passphrase)
        proc.stdin.close()
        if proc.wait() != 0:
            raise ValueError("signcode didn't return with 0")
        stdout.seek(0)
        data = stdout.read()
        # Make sure that the command output "Succeeded".  Sometimes signcode
        # returns with 0, but doesn't output "Succeeded", which in the past has
        # meant that the file has been signed, but is missing a timestmap.
        if data.strip() != "Succeeded" and "Success" not in data:
            raise ValueError("signcode didn't report success")
    except:
        stdout.seek(0)
        data = stdout.read()
        log.exception(data)
        raise

    # Regenerate any .chk files that are now invalid
    if getChkFile(filename):
        stdout = tempfile.TemporaryFile()
        try:
            command = ['shlibsign', '-v', '-i', basename]
            check_call(command, cwd=dirname, stdout=stdout, stderr=STDOUT)
            stdout.seek(0)
            data = stdout.read()
            if "signature: 40 bytes" not in data:
                raise ValueError("shlibsign didn't generate signature")
        except:
            stdout.seek(0)
            data = stdout.read()
            log.exception(data)
            raise


def getfile(baseurl, filehash, format_):
    url = "%s/sign/%s/%s" % (baseurl, format_, filehash)
    log.debug("%s: GET %s", filehash, url)
    r = urllib2.Request(url)
    return urllib2.urlopen(r)

def remote_signfile(options, url, filename, fmt, token, dest=None):
    filehash = sha1sum(filename)
    if dest is None:
        dest = filename

    if fmt == 'gpg':
        dest += '.asc'

    parent_dir = os.path.dirname(os.path.abspath(dest))
    if not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    # Check the cache
    cached_fn = None
    if options.cachedir:
        log.debug("%s: checking cache", filehash)
        cached_fn = os.path.join(options.cachedir, fmt, filehash)
        if os.path.exists(cached_fn):
            log.info("%s: exists in the cache; copying to %s", filehash, dest)
            cached_fp = open(cached_fn, 'rb')
            tmpfile = dest + '.tmp'
            fp = open(tmpfile, 'wb')
            hsh = hashlib.new('sha1')
            while True:
                data = cached_fp.read(1024**2)
                if not data:
                    break
                hsh.update(data)
                fp.write(data)
            fp.close()
            newhash = hsh.hexdigest()
            if os.path.exists(dest):
                os.unlink(dest)
            os.rename(tmpfile, dest)
            log.info("%s: OK", filehash)
            # See if we should re-sign NSS
            if options.nsscmd and filehash != newhash and os.path.exists(os.path.splitext(filename)[0] + ".chk"):
                cmd = '%s "%s"' % (options.nsscmd, dest)
                log.info("Regenerating .chk file")
                log.debug("Running %s", cmd)
                check_call(cmd, shell=True)
            return True

    log.info("%s: processing %s on %s", filehash, filename, url)

    errors = 0
    pendings = 0
    max_errors = 20
    max_pending_tries = 300
    while True:
        if pendings >= max_pending_tries:
            log.error("%s: giving up after %i tries", filehash, pendings)
            return False
        if errors >= max_errors:
            log.error("%s: giving up after %i tries", filehash, errors)
            return False
        # Try to get a previously signed copy of this file
        try:
            req = getfile(url, filehash, fmt)
            headers = req.info()
            responsehash = headers['X-SHA1-Digest']
            tmpfile = dest + '.tmp'
            fp = open(tmpfile, 'wb')
            while True:
                data = req.read(1024**2)
                if not data:
                    break
                fp.write(data)
            fp.close()
            newhash = sha1sum(tmpfile)
            if newhash != responsehash:
                log.warn("%s: hash mismatch; trying to download again", filehash)
                os.unlink(tmpfile)
                errors += 1
                continue
            if os.path.exists(dest):
                os.unlink(dest)
            os.rename(tmpfile, dest)
            log.info("%s: OK", filehash)
            # See if we should re-sign NSS
            if options.nsscmd and filehash != responsehash and os.path.exists(os.path.splitext(filename)[0] + ".chk"):
                cmd = '%s "%s"' % (options.nsscmd, dest)
                log.info("Regenerating .chk file")
                log.debug("Running %s", cmd)
                check_call(cmd, shell=True)

            # Possibly write to our cache
            if cached_fn:
                cached_dir = os.path.dirname(cached_fn)
                if not os.path.exists(cached_dir):
                    log.debug("Creating %s", cached_dir)
                    os.makedirs(cached_dir)
                log.info("Copying %s to cache %s", dest, cached_fn)
                copyfile(dest, cached_fn)
            break
        except urllib2.HTTPError, e:
            try:
                if 'X-Pending' in e.headers:
                    log.debug("%s: pending; try again in a bit", filehash)
                    time.sleep(1)
                    pendings += 1
                    continue
            except:
                raise

            errors += 1

            # That didn't work...so let's upload it
            log.info("%s: uploading for signing", filehash)
            req = None
            try:
                try:
                    nonce = open(options.noncefile, 'rb').read()
                except IOError:
                    nonce = ""
                req = uploadfile(url, filename, fmt, token, nonce=nonce)
                nonce = req.info()['X-Nonce']
                open(options.noncefile, 'wb').write(nonce)
            except urllib2.HTTPError, e:
                # python2.5 doesn't think 202 is ok...but really it is!
                if 'X-Nonce' in e.headers:
                    log.debug("updating nonce")
                    nonce = e.headers['X-Nonce']
                    open(options.noncefile, 'wb').write(nonce)
                if e.code != 202:
                    log.info("%s: error uploading file for signing: %s", filehash, e.msg)
            except (urllib2.URLError, socket.error, httplib.BadStatusLine):
                # Try again in a little while
                log.info("%s: connection error; trying again soon", filehash)
            time.sleep(1)
            continue
        except (urllib2.URLError, socket.error):
            # Try again in a little while
            log.info("%s: connection error; trying again soon", filehash)
            time.sleep(1)
            errors += 1
            continue
    return True

def find_files(options, args):
    retval = []
    for fn in args:
        if os.path.isdir(fn):
            dirname = fn
            for root, dirs, files in os.walk(dirname):
                for f in files:
                    fullpath = os.path.join(root, f)
                    if not any(fnmatch.fnmatch(f, pat) for pat in options.includes):
                        log.debug("Skipping %s; doesn't match any include pattern", f)
                        continue
                    if any(fnmatch.fnmatch(f, pat) for pat in options.excludes):
                        log.debug("Skipping %s; matches an exclude pattern", f)
                        continue
                    retval.append(fullpath)
        else:
            retval.append(fn)
    return retval

def relpath(d1, d2):
    """Returns d1 relative to d2"""
    assert d1.startswith(d2)
    return d1[len(d2):].lstrip('/')

def buildValidatingOpener(ca_certs):
    """Build and register an HTTPS connection handler that validates that we're
    talking to a host matching ca_certs (a file containing a list of
    certificates we accept.

    Subsequent calls to HTTPS urls will validate that we're talking to an acceptable server.
    """
    try:
        from poster.streaminghttp import StreamingHTTPSHandler as HTTPSHandler, \
                StreamingHTTPSConnection as HTTPSConnection
        assert HTTPSHandler # pyflakes
        assert HTTPSConnection # pyflakes
    except ImportError:
        from httplib import HTTPSConnection
        from urllib2 import HTTPSHandler

    import ssl

    class VerifiedHTTPSConnection(HTTPSConnection):
        def connect(self):
            # overrides the version in httplib so that we do
            #    certificate verification
            #sock = socket.create_connection((self.host, self.port),
                                            #self.timeout)
            #if self._tunnel_host:
                #self.sock = sock
                #self._tunnel()

            sock = socket.socket()
            sock.connect((self.host, self.port))

            # wrap the socket using verification with the root
            #    certs in trusted_root_certs
            self.sock = ssl.wrap_socket(sock,
                                        self.key_file,
                                        self.cert_file,
                                        cert_reqs=ssl.CERT_REQUIRED,
                                        ca_certs=ca_certs,
                                        )

    # wraps https connections with ssl certificate verification
    class VerifiedHTTPSHandler(HTTPSHandler):
        def __init__(self, connection_class=VerifiedHTTPSConnection):
            self.specialized_conn_class = connection_class
            HTTPSHandler.__init__(self)

        def https_open(self, req):
            return self.do_open(self.specialized_conn_class, req)

    https_handler = VerifiedHTTPSHandler()
    opener = urllib2.build_opener(https_handler)
    urllib2.install_opener(opener)

def uploadfile(baseurl, filename, format_, token, nonce):
    """Uploads file (given by `filename`) to server at `baseurl`.

    `sesson_key` and `nonce` are string values that get passed as POST
    parameters.
    """
    from poster.encode import multipart_encode
    filehash = sha1sum(filename)

    try:
        fp = open(filename, 'rb')

        params = {
                'filedata': fp,
                'sha1': filehash,
                'filename': os.path.basename(filename),
                'token': token,
                'nonce': nonce,
                }

        datagen, headers = multipart_encode(params)
        r = urllib2.Request("%s/sign/%s" % (baseurl, format_), datagen, headers)
        return urllib2.urlopen(r)
    finally:
        fp.close()

def gpg_signfile(filename, sigfile, gpgdir, fake=False, passphrase=None):
    """Sign the given file with the default key from gpgdir. The signature is
    written to sigfile.

    If fake is True, generate a fake signature and sleep for a bit.

    If passphrase is set, it will be passed to gpg on stdin
    """
    if fake:
        open(sigfile, "wb").write("""
-----BEGIN FAKE SIGNATURE-----
Version: 1.2.3.4

I am ur signature!
-----END FAKE SIGNATURE-----""")
        time.sleep(1)
        return

    command = ['gpg', '--homedir', gpgdir, '-bsa', '-o', sigfile, '-q', '--batch']
    if passphrase:
        command.extend(['--passphrase-fd', '0'])
    command.append(filename)
    log.info('Running %s', command)
    stdout = tempfile.TemporaryFile()
    try:
        proc = Popen(command, stdout=stdout, stderr=STDOUT, stdin=PIPE)
        if passphrase:
            proc.stdin.write(passphrase)
        proc.stdin.close()
        if proc.wait() != 0:
            raise ValueError("gpg didn't return 0")
        stdout.seek(0)
        data = stdout.read()
    except:
        stdout.seek(0)
        data = stdout.read()
        log.exception(data)
        raise

def safe_unlink(filename):
    """unlink filename ignorning errors if the file doesn't exist"""
    try:
        if os.path.isdir(filename):
            for root, dirs, files in os.walk(filename, topdown=True):
                for f in files:
                    fp = os.path.join(root, f)
                    safe_unlink(fp)
                os.rmdir(root)
        else:
            os.unlink(filename)
    except OSError, e:
        # Ignore "No such file or directory"
        if e.errno == 2:
            return
        else:
            raise

def mar_signfile(inputfile, outputfile, mar_cmd, fake=False, passphrase=None):
    # Now sign it
    if isinstance(mar_cmd, basestring):
        mar_cmd = shlex.split(mar_cmd)
    else:
        mar_cmd = mar_cmd[:]
    command = mar_cmd + [inputfile, outputfile]
    log.info('Running %s', command)
    stdout = tempfile.TemporaryFile()
    try:
        proc = Popen(command, stdout=stdout, stderr=STDOUT, stdin=PIPE)
        if passphrase:
            proc.stdin.write(passphrase)
            proc.stdin.write("\n")
        proc.stdin.close()
        if proc.wait() != 0:
            raise ValueError("mar didn't return 0")
        stdout.seek(0)
        data = stdout.read()
    except:
        stdout.seek(0)
        data = stdout.read()
        log.exception(data)
        raise

def dmg_signfile(filename, keychain, signing_identity, code_resources, lockfile, fake=False, passphrase=None):
    """ Sign a mac .app folder
    """
    from flufl.lock import Lock, AlreadyLockedError, TimeOutError, NotLockedError
    from datetime import timedelta
    import pexpect

    basename = os.path.basename(filename)
    dirname = os.path.dirname(filename)
    stdout = tempfile.TemporaryFile()

    sign_command = ['codesign',
        '-s', signing_identity, '-fv',
        '--keychain', keychain,
        '--resource-rules', code_resources,
        basename]

    # pexpect requires a string as input
    unlock_command = 'security unlock-keychain '+keychain
    lock_command = ['security', 'lock-keychain', keychain]
    try:
        sign_lock = None
        try: 
            # Acquire a lock for the signing command, to ensure we don't have a 
            # race condition where one process locks the keychain immediately after another
            # unlocks it.
            log.debug("Try to acquire %s", lockfile)
            sign_lock = Lock(lockfile)
            # Put a 30 second timeout on waiting for the lock. 
            sign_lock.lock(timedelta(0,30))

            # Unlock the keychain so that we do not get a user-interaction prompt to use
            # the keychain for signing. This operation requires a password.
            child = pexpect.spawn (unlock_command)
            child.expect('password to unlock .*')
            child.sendline(passphrase)
            # read output until child exits
            child.read()
            child.close()
            if child.exitstatus != 0:
                raise ValueError("keychain unlock failed")

            # Execute the signing command
            check_call(sign_command, cwd=dirname, stdout=stdout, stderr=STDOUT)

        except TimeOutError, error:
            # timed out acquiring lock, give an error
            log.exception("Timeout acquiring lock  %s for codesign, is something broken? ", lockfile, error)
            raise
        except:
            # catch any other locking error
            log.exception("Error acquiring  %s for codesign, is something broken?", lockfile)
            raise
        finally: 
            # Lock the keychain again, no matter what happens
            # This command does not require a password
            check_call(lock_command)

            # Release the lock, if it was acquired
            if sign_lock:
                try:
                    sign_lock.unlock()
                    log.debug("Release %s", lockfile)
                except NotLockedError:
                    log.debug("%s was already unlocked", lockfile)

    except:
        stdout.seek(0)
        data = stdout.read()
        log.exception(data)
        raise

def dmg_signpackage(pkgfile, dstfile, keychain, mac_id, fake=False, passphrase=None):
    """ Sign a mac build, putting results into `dstfile`.
        pkgfile must be a tar, which gets unpacked, signed, and repacked.
    """
    # Keep track of our output in a list here, and we can output everything
    # when we're done This is to avoid interleaving the output from
    # multiple processes.

    #TODO: Is it even possible to do 'fake' signing?
    logs = []
    logs.append("Repacking %s to %s" % (pkgfile, dstfile))

    tmpdir = tempfile.mkdtemp()
    pkgdir = os.path.dirname(pkgfile)
    filename = os.path.basename(pkgfile)
    try:
        # Unpack it
        logs.append("Unpacking %s to %s" % (pkgfile, tmpdir))
        unpacktar(pkgfile, tmpdir)

        for macdir in os.listdir(tmpdir):
            macdir = os.path.join(tmpdir, macdir)
            log.debug('Checking if we should sign %s', macdir)
            if shouldSign(macdir, 'mac'):
                log.debug('Signing %s', macdir)

                # Grab the code resources file. Need to find the filename
                code_resources =  macdir + "/Contents/_CodeSignature/CodeResources"
                lockfile = os.path.join(pkgdir, '.lock')

                dmg_signfile(macdir, keychain, mac_id, code_resources, lockfile, passphrase=passphrase)

        # Repack it
        logs.append("Packing %s" % dstfile)
        tar_dir(dstfile, tmpdir)
    except:
        log.exception("Error signing %s", pkgfile)
        return False
    finally:
        # Clean up after ourselves, and output our logs
        shutil.rmtree(tmpdir)
        log.info("\n  ".join(logs))


