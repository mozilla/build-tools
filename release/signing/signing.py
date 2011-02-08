import tempfile, os, hashlib, shutil, bz2, re, sys
import logging
from subprocess import *

log = logging.getLogger()

SEVENZIP = os.environ.get('SEVENZIP', '7z')
MAR = os.environ.get('MAR', 'mar')

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
            m = re.search("update/(win32|linux-i686|linux-x86_64|mac|mac64)/([-a-zA-Z]+)/(%s)-(\d+\.\d+(?:\.\d+)?(?:\w+\d+)?)\.(complete)\.mar" % product, filepath)
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
            # EUBallot builds use a different enough style of path than others
            # that we can't catch them in the same regexp
            if filepath.find('win32-EUBallot') != -1:
                ret['platform'] = 'win32'
                m = re.search("(win32-EUBallot/)([-a-zA-Z]+)/((?i)%s) Setup (\d+\.\d+(?:\.\d+)?(?:\w+\d+)?(?:\ \w+\ \d+)?)\.exe" % product, filepath)
                if not m:
                    raise ValueError("Could not parse: %s" % filepath)
                ret['leading_path'] = m.group(1)
                ret['locale'] = m.group(2)
                ret['product'] = m.group(3).lower()
                ret['version'] = m.group(4)
            else:
                m = re.search("(partner-repacks/[-a-zA-Z0-9_]+/|)(win32|mac|linux-i686)/([-a-zA-Z]+)/((?i)%s) Setup (\d+\.\d+(?:\.\d+)?(?:\w+\d+)?(?:\ \w+\ \d+)?)\.exe" % product, filepath)
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
    fp = open(f)
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
    f = open(filename, "w")
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
    f = open(tmpfile)
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

def unpackfile(filename, destdir):
    """Unpack a mar or exe into destdir"""
    if filename.endswith(".mar"):
        return unpackmar(filename, destdir)
    elif filename.endswith(".exe"):
        return unpackexe(filename, destdir)
    else:
        raise ValueError("Unknown file type: %s" % filename)

def packfile(filename, srcdir):
    """Package up srcdir into filename, archived with 7z for exes or mar for
    mar files"""
    if filename.endswith(".mar"):
        return packmar(filename, srcdir)
    elif filename.endswith(".exe"):
        return packexe(filename, srcdir)
    else:
        raise ValueError("Unknown file type: %s" % filename)

def shouldSign(filename):
    """Returns True if filename should be signed."""
    # We don't sign these files here, since it would invalidate the
    # .chk files
    _dont_sign = ['freebl3.dll', 'softokn3.dll', 'nssdbm3.dll']
    ext = os.path.splitext(filename)[1]
    b = os.path.basename(filename)
    if ext in ('.dll', '.exe') and b not in _dont_sign:
        return True
    return False

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
