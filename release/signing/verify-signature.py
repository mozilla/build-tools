#!/usr/bin/python
# Verifies that a directory of signed files matches a corresponding directory
# of unsigned files
import tempfile
import random
from subprocess import call

from signing import *

def check_repack(unsigned, signed, binary_checksums, fake_signatures=False,
        product="firefox"):
    """Check that files `unsigned` and `signed` match.  They will both be
    unpacked and their contents compared.

    Verifies that all non-signable files are unmodified and have the same
    permissions.  If fake_signatures is True, then the files in `signed` aren't
    actually signed, so they're compared to the unsigned ones to make sure
    they're identical as well.

    If fake_signatures is False, then chktrust is used to verify that signed
    files have valid signatures.

    binary_checksums contains a dict of filenames to sha1sums. These are
    stored and used for verification inside locales across installers and MARs
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

            # Check the file signatures and also store the file checksums for
            # comparison against the corresponding file in the installer/MAR
            # pair
            if not fake_signatures and shouldSign(uf):
                d = os.path.dirname(sf)
                nullfd = open(os.devnull, "w")
                if 0 != call(['chktrust', '-q', b], cwd=d, stdout=nullfd):
                    return False, "Bad signature %s in %s (%s)" % (f, signed, cygpath(sf))
                else:
                    # store checksum for signed binary for later verification
                    binary_checksums[b] = sha1sum(sf)
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

def verify_checksums(sums):
    """ Verify checksums for signed binaries across installer/MAR pairs """
    valid_checksum = True
    log.info("Verifying checksums of MARs and installers match")
    for locale in sums.keys():
        packages = sums[locale]
        log.info("Comparing packages for locale: %s", locale)
        for p in packages.keys():
            log.info(" - %s ", p)
        # Use MARs as a base for comparison as the installer has files not
        # common to the update
        mar = [p for p in packages.keys() if p.endswith('.mar')]
        if not mar:
            log.error("Error, no update available for this locale")
            valid_checksum = False
            continue
        if not sums_are_equal(packages[mar[0]], [packages[s] for s in packages.keys()]):
            log.error("Error: MARs and installer contents do not match")
            valid_checksum = False
    return valid_checksum

def setup_checksums(checksums, unsigned_file, product):
    """ Set up dictionary nesting to uniquely identify the file being
    examined."""
    info = fileInfo(unsigned_file, product)
    if info['locale'] not in checksums.keys():
        checksums[info['locale']] = {}
    checksums[info['locale']][unsigned_file] = {}
    pkg_checksums = checksums[info['locale']][unsigned_file]

    # return reference to a sub-dict uniquely identifying this particular
    # container
    return pkg_checksums

def filter_quick(unsigned, first_locale, product):
    """ Trim down the list of files to verify to only the firstLocale (en-US
    by default), one l10n repack (locale selected at random), one
    partner-repack with firstLocale (selected at random) and one
    partner-repack with the random locale"""
    # Select a locale at random that is not the first_locale, and has at
    # least one available partner repack built
    rand_locale = fileInfo(
        random.choice([f for f in unsigned if first_locale not in f and
            fileInfo(f, product)['leading_path']]),
        product)['locale']
    rand_first_partner = fileInfo(
        random.choice([f for f in unsigned if first_locale in f]),
        product)['leading_path']
    rand_locale_partner = fileInfo(
        random.choice([f for f in unsigned if rand_locale in f]),
        product)['leading_path']
    return [f for f in unsigned
        if (first_locale == fileInfo(f, product)['locale'] or
            rand_locale == fileInfo(f, product)['locale']) and
            (not fileInfo(f, product)['leading_path'] or
            fileInfo(f, product)['leading_path'] == rand_first_partner or
            fileInfo(f, product)['leading_path'] == rand_locale_partner)]

if __name__ == "__main__":
    import sys, os, logging
    from optparse import OptionParser

    parser = OptionParser("%prog [--fake] [--product <product>] unsigned-dir signed-dir")
    parser.set_defaults(
            fake=False,
            abortOnFail=False,
            product="firefox",
            first_locale='en-US',
            quick=False,
            )
    parser.add_option("", "--fake", dest="fake", action="store_true", help="Don't verify signatures, just compare file hashes")
    parser.add_option("", "--abort-on-fail", dest="abortOnFail", action="store_true", help="Stop processing after the first error")
    parser.add_option("", "--product", dest="product", help="product name")
    parser.add_option("", "--first-locale", dest="first_locale",
        help="first locale to check")
    parser.add_option("", "--quick-verify", dest="quick", action="store_true",
        help="Verify only first locale and one random additional locale")

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
    unsigned_files = sortFiles(filterFiles(unsigned_files, options.product),
        options.product, options.first_locale)
    # Perform a partial verification
    if options.quick:
        unsigned_files = filter_quick(unsigned_files, options.first_locale,
            options.product)

    failed = False
    all_checksums = {}
    for uf in unsigned_files[:]:
        sf = convertPath(uf, signed_dir)
        repack_checksums = setup_checksums(all_checksums, uf, options.product)
        # repack_checksums is a reference to a sub-dict in
        # all_checksums[locale][format], so when check_repack fills it with
        # the checksums of the package internals for the current file,
        # all_checksums gets populated
        result, msg = check_repack(uf, sf, repack_checksums, options.fake,
            options.product)
        print sf, result, msg
        if not result:
            failed = True
            if options.abortOnFail:
                sys.exit(1)
    # Now that we have the checksums for the internals of every locale and
    # format, we can verify them against each other across formats for each
    # locale.
    if not verify_checksums(all_checksums):
        failed = True

    if failed:
        sys.exit(1)
