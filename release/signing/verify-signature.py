#!/usr/bin/python
# Verifies that a directory of signed files matches a corresponding directory
# of unsigned files
import tempfile
from subprocess import call

from signing import *

def check_repack(unsigned, signed, fake_signatures=False, product="firefox"):
    """Check that files `unsigned` and `signed` match.  They will both be
    unpacked and their contents compared.

    Verifies that all non-signable files are unmodified and have the same
    permissions.  If fake_signatures is True, then the files in `signed` aren't
    actually signed, so they're compared to the unsigned ones to make sure
    they're identical as well.

    If fake_signatures is False, then chktrust is used to verify that signed
    files have valid signatures.
    """
    if not os.path.exists(unsigned):
        return False, "%s doesn't exist" % unsigned
    if not os.path.exists(signed):
        return False, "%s doesn't exist" % signed
    unsigned_dir = os.path.abspath(tempfile.mkdtemp())
    signed_dir = os.path.abspath(tempfile.mkdtemp())
    try:
        # Unpack both files
        unpackfile(unsigned, unsigned_dir)
        unpackfile(signed, signed_dir)

        unsigned_files = sorted([f[len(unsigned_dir)+1:] for f in findfiles(unsigned_dir)])
        signed_files = sorted([f[len(signed_dir)+1:] for f in findfiles(signed_dir)])

        unsigned_dirs = sorted([d[len(unsigned_dir)+1:] for d in finddirs(unsigned_dir)])
        signed_dirs = sorted([d[len(signed_dir)+1:] for d in finddirs(signed_dir)])

        # Make sure the list of files are the same
        if signed_files != unsigned_files:
            new_files = ",".join(set(signed_files) - set(unsigned_files))
            removed_files = ",".join(set(unsigned_files) - set(signed_files))
            return False, """List of files differs:
Added: %(new_files)s
Missing: %(removed_files)s""" % locals()

        # And the list of directories too
        if signed_dirs != unsigned_dirs:
            new_dirs = ",".join(set(signed_dirs) - set(unsigned_dirs))
            removed_dirs = ",".join(set(unsigned_dirs) - set(signed_dirs))
            return False, """List of directories differs:
Added: %(new_dirs)s
Missing: %(removed_dirs)s""" % locals()

        # Check the directory modes
        for d in unsigned_dirs:
            ud = os.path.join(unsigned_dir, d)
            sd = os.path.join(signed_dir, d)
            if os.stat(sd).st_mode != os.stat(ud).st_mode:
                return False, "Mode mismatch (%o != %o) in %s" % (os.stat(ud).st_mode, os.stat(sd).st_mode, d)

        info = fileInfo(signed, product)

        for f in unsigned_files:
            sf = os.path.join(signed_dir, f)
            uf = os.path.join(unsigned_dir, f)
            b = os.path.basename(sf)
            if info['format'] == 'mar':
                # Need to decompress this first
                bunzip2(sf)
                bunzip2(uf)

            # Check the file mode
            if os.stat(sf).st_mode != os.stat(uf).st_mode:
                return False, "Mode mismatch (%o != %o) in %s" % (os.stat(uf).st_mode, os.stat(sf).st_mode, f)

            # Check the file signatures
            if not fake_signatures and shouldSign(uf):
                d = os.path.dirname(sf)
                nullfd = open(os.devnull, "w")
                if 0 != call(['chktrust', '-q', b], cwd=d, stdout=nullfd):
                    return False, "Bad signature %s in %s (%s)" % (f, signed, cygpath(sf))
                else:
                    log.debug("%s OK", b)
            else:
                # Check the hashes
                if f == "update.manifest":
                    sf_lines = sorted(open(sf).readlines())
                    uf_lines = sorted(open(uf).readlines())
                    if sf_lines != uf_lines:
                        return False, "update.manifest differs"
                    log.debug("%s OK", b)
                elif sha1sum(sf) != sha1sum(uf):
                    return False, "sha1sum on %s differs" % f
                else:
                    log.debug("%s OK", b)

        return True, "OK"
    finally:
        shutil.rmtree(unsigned_dir)
        shutil.rmtree(signed_dir)

if __name__ == "__main__":
    import sys, os, logging
    from optparse import OptionParser

    parser = OptionParser("%prog [--fake] unsigned-dir signed-dir")
    parser.set_defaults(
            fake=False,
            abortOnFail=False,
            )
    parser.add_option("", "--fake", dest="fake", action="store_true", help="Don't verify signatures, just compare file hashes")
    parser.add_option("", "--abort-on-fail", dest="abortOnFail", action="store_true", help="Stop processing after the first error")

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        checkTools()
    except OSError,e:
        parser.error(e.message)

    options, args = parser.parse_args()
    if len(args) != 2:
        parser.error("Must specify two arguments: unsigned-dir, and signed-dir")

    # Compare each signed .mar/.exe to the unsigned .mar/.exe
    unsigned_dir = args[0]
    signed_dir = args[1]
    unsigned_files = findfiles(unsigned_dir)
    unsigned_files.sort()
    failed = False
    for uf in unsigned_files[:]:
        if 'win32' not in uf:
            continue
        if not uf.endswith(".mar") and not uf.endswith(".exe"):
            continue
        sf = convertPath(uf, signed_dir)
        result, msg = check_repack(uf, sf, options.fake)
        print sf, result, msg
        if not result:
            failed = True
            if options.abortOnFail:
                sys.exit(1)

    if failed:
        sys.exit(1)
