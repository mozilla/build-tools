#!/usr/bin/python

# This script expects a directory as its first non-option argument,
# followed by a list of filenames.

import sys, os, os.path, shutil, re
from optparse import OptionParser
from time import mktime, strptime
from errno import EEXIST

NIGHTLY_PATH = "/home/ftp/pub/%(product)s/%(nightly_dir)s"
TINDERBOX_BUILDS_PATH = "/home/ftp/pub/%(product)s/tinderbox-builds/%(tinderbox_builds_dir)s"
LONG_DATED_DIR = "%(year)s/%(month)s/%(year)s-%(month)s-%(day)s-%(hour)s-%(branch)s"
SHORT_DATED_DIR = "%(year)s-%(month)s-%(day)s-%(hour)s-%(branch)s"
CANDIDATES_DIR = "%(version)s-candidates/build%(buildnumber)s"
LATEST_DIR = "latest-%(branch)s"
# Production configs that need to be commented out when doing staging.
TINDERBOX_URL_PATH = "http://stage.mozilla.org/pub/mozilla.org/%(product)s/tinderbox-builds/%(tinderbox_builds_dir)s"
CANDIDATES_URL_PATH = "http://stage.mozilla.org/pub/mozilla.org/%(product)s/%(nightly_dir)s/%(version)s-candidates/build%(buildnumber)s"
SHADOW_CENTRAL_URL_PATH = "https://ftp.mozilla.org/pvt-builds/%(product)s/shadow-central-builds/%(tinderbox_builds_dir)s"
SHADOW_CENTRAL_DIR = "/home/ftp/pub/firefox/pvt-builds/%(product)s/shadow-central-builds/%(tinderbox_builds_dir)s"
TRYSERVER_DIR = "/home/ftp/pub/%(product)s/tryserver-builds/%(who)s-%(revision)s/%(builddir)s"
TRYSERVER_URL_PATH = "http://stage.mozilla.org/pub/mozilla.org/%(product)s/tryserver-builds/%(who)s-%(revision)s/%(builddir)s"
# Staging configs start here.  Uncomment when working on staging
#TINDERBOX_URL_PATH = "http://staging-stage.build.mozilla.org/pub/mozilla.org/%(product)s/tinderbox-builds/%(tinderbox_builds_dir)s"
#CANDIDATES_URL_PATH = "http://staging-stage.build.mozilla.org/pub/mozilla.org/%(product)s/%(nightly_dir)s/%(version)s-candidates/build%(buildnumber)s"
#TRYSERVER_DIR = "/home/ftp/pub/%(product)s/tryserver-builds/%(who)s-%(revision)s/%(builddir)s"
#TRYSERVER_URL_PATH = "http://staging-stage.build.mozilla.org/pub/mozilla.org/%(product)s/tryserver-builds/%(who)s-%(revision)s/%(builddir)s"

PARTIAL_MAR_RE = re.compile('\.partial\..*\.mar$')

def CopyFileToDir(original_file, source_dir, dest_dir, preserve_dirs=False):
    if not original_file.startswith(source_dir):
        print "%s is not in %s!" % (original_file, source_dir)
        return
    relative_path = os.path.basename(original_file)
    if preserve_dirs:
        # Add any dirs below source_dir to the final destination
        filePath = original_file.replace(source_dir, "").lstrip("/")
        filePath = os.path.dirname(filePath)
        dest_dir = os.path.join(dest_dir, filePath)
    new_file = os.path.join(dest_dir, relative_path)
    full_dest_dir = os.path.dirname(new_file)
    if not os.path.isdir(full_dest_dir):
        try:
            os.makedirs(full_dest_dir, 0755)
        except OSError, e:
            if e.errno == EEXIST:
                print "%s already exists, continuing anyways" % full_dest_dir
            else:
                raise
    if os.path.exists(new_file):
        os.unlink(new_file)
    shutil.copyfile(original_file, new_file)

def BuildIDToDict(buildid):
    """Returns an dict with the year, month, day, hour, minute, and second
       as keys, as parsed from the buildid"""
    buildidDict = {}
    try:
        # strptime is no good here because it strips leading zeros
        buildidDict['year']   = buildid[0:4]
        buildidDict['month']  = buildid[4:6]
        buildidDict['day']    = buildid[6:8]
        buildidDict['hour']   = buildid[8:10]
        buildidDict['minute'] = buildid[10:12]
        buildidDict['second'] = buildid[12:14]
    except:
        raise "Could not parse buildid!"
    return buildidDict

def BuildIDToUnixTime(buildid):
    """Returns the timestamp the buildid represents in unix time."""
    try:
        return int(mktime(strptime(buildid, "%Y%m%d%H%M%S")))
    except:
        raise "Could not parse buildid!"

def ReleaseToDated(options, upload_dir, files):
    values = BuildIDToDict(options.buildid)
    values['branch']  = options.branch
    longDir = LONG_DATED_DIR % values
    shortDir = SHORT_DATED_DIR % values

    longDatedPath = os.path.join(NIGHTLY_PATH, longDir)
    shortDatedPath = os.path.join(NIGHTLY_PATH, shortDir)

    for f in files:
        if f.endswith('crashreporter-symbols.zip'):
            continue
        CopyFileToDir(f, upload_dir, longDatedPath)
    os.utime(longDatedPath, None)

    try:
        cwd = os.getcwd()
        os.chdir(NIGHTLY_PATH)
        if not os.path.exists(shortDir):
            os.symlink(longDir, shortDir)
    finally:
        os.chdir(cwd)

def ReleaseToLatest(options, upload_dir, files):
    latestDir = LATEST_DIR % {'branch': options.branch}
    latestPath = os.path.join(NIGHTLY_PATH, latestDir)

    for f in files:
        if f.endswith('crashreporter-symbols.zip'):
            continue
        if PARTIAL_MAR_RE.search(f):
            continue
        CopyFileToDir(f, upload_dir, latestPath)
    os.utime(latestPath, None)

def ReleaseToBuildDir(builds_dir, builds_url, options, upload_dir, files, dated):
    tinderboxBuildsPath = builds_dir % \
      {'product': options.product,
       'tinderbox_builds_dir': options.tinderbox_builds_dir}
    tinderboxUrl = builds_url % \
      {'product': options.product,
       'tinderbox_builds_dir': options.tinderbox_builds_dir}
    if dated:
        buildid = str(BuildIDToUnixTime(options.buildid))
        tinderboxBuildsPath = os.path.join(tinderboxBuildsPath, buildid)
        tinderboxUrl = os.path.join(tinderboxUrl, buildid)

    for f in files:
        # Reject MAR files. They don't belong here.
        if f.endswith('.mar'):
            continue
        CopyFileToDir(f, upload_dir, tinderboxBuildsPath)
        sys.stderr.write("%s\n" % os.path.join(tinderboxUrl, os.path.basename(f)))
    os.utime(tinderboxBuildsPath, None)

def ReleaseToTinderboxBuilds(options, upload_dir, files, dated=True):
    ReleaseToBuildDir(TINDERBOX_BUILDS_PATH, TINDERBOX_URL_PATH, options, upload_dir, files, dated)

def ReleaseToShadowCentralBuilds(options, upload_dir, files, dated=True):
    ReleaseToBuildDir(SHADOW_CENTRAL_DIR, SHADOW_CENTRAL_URL_PATH, options, upload_dir, files, dated)
        
def ReleaseToTinderboxBuildsOverwrite(options, upload_dir, files):
    ReleaseToTinderboxBuilds(options, upload_dir, files, dated=False)

def ReleaseToCandidatesDir(options, upload_dir, files):
    candidatesDir = CANDIDATES_DIR % {'version': options.version,
                                      'buildnumber': options.build_number}
    candidatesPath = os.path.join(NIGHTLY_PATH, candidatesDir)
    candidatesUrl = CANDIDATES_URL_PATH % {
            'nightly_dir': options.nightly_dir,
            'version': options.version,
            'buildnumber': options.build_number,
            'product': options.product,
            }

    for f in files:
        realCandidatesPath = candidatesPath
        if 'win32' in f:
            realCandidatesPath = os.path.join(realCandidatesPath, 'unsigned')
            url = os.path.join(candidatesUrl, 'unsigned')
        else:
            url = candidatesUrl
        CopyFileToDir(f, upload_dir, realCandidatesPath, preserve_dirs=True)
        # Output the URL to the candidate build
        if f.startswith(upload_dir):
            relpath = f[len(upload_dir):].lstrip("/")
        else:
            relpath = f.lstrip("/")

        sys.stderr.write("%s\n" % os.path.join(url, relpath))
        # We always want release files chmod'ed this way so other users in
        # the group cannot overwrite them.
        os.chmod(f, 0644)

    # Same thing for directories, but 0755
    for root,dirs,files in os.walk(candidatesPath):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0755)

def ReleaseToTryserverBuilds(options, upload_dir, files):
    tryserverBuildsPath = TRYSERVER_DIR % {'product': options.product,
                                           'who': options.who,
                                           'revision': options.revision,
                                           'builddir': options.builddir}
    tryserverBuildsUrl = TRYSERVER_URL_PATH % {'product': options.product,
                                               'who': options.who,
                                               'revision': options.revision,
                                               'builddir': options.builddir}
    for f in files:
        CopyFileToDir(f, upload_dir, tryserverBuildsPath)
        sys.stderr.write("%s\n" % os.path.join(tryserverBuildsUrl, os.path.basename(f)))

if __name__ == '__main__':
    releaseTo = []
    error = False
    
    parser = OptionParser(usage="usage: %prog [options] <directory> <files>")
    parser.add_option("-p", "--product",
                      action="store", dest="product",
                      help="Set product name to build paths properly.")
    parser.add_option("-v", "--version",
                      action="store", dest="version",
                      help="Set version number to build paths properly.")
    parser.add_option("--nightly-dir", default="nightly",
                      action="store", dest="nightly_dir",
                      help="Set the base directory for nightlies (ie $product/$nightly_dir/), and the parent directory for release candidates (default 'nightly').")
    parser.add_option("-b", "--branch",
                      action="store", dest="branch",
                      help="Set branch name to build paths properly.")
    parser.add_option("-i", "--buildid",
                      action="store", dest="buildid",
                      help="Set buildid to build paths properly.")
    parser.add_option("-n", "--build-number",
                      action="store", dest="build_number",
                      help="Set buildid to build paths properly.")
    parser.add_option("-r", "--revision",
                      action="store", dest="revision")
    parser.add_option("-w", "--who",
                      action="store", dest="who")
    parser.add_option("--builddir",
                      action="store", dest="builddir",
                      help="Subdir to arrange packaged unittest build paths properly.")
    parser.add_option("--tinderbox-builds-dir",
                      action="store", dest="tinderbox_builds_dir",
                      help="Set tinderbox builds dir to build paths properly.")
    parser.add_option("-l", "--release-to-latest",
                      action="store_true", dest="release_to_latest",
                      help="Copy files to $product/$nightly_dir/latest-$branch")
    parser.add_option("-d", "--release-to-dated",
                      action="store_true", dest="release_to_dated",
                      help="Copy files to $product/$nightly_dir/$datedir-$branch")
    parser.add_option("-c", "--release-to-candidates-dir",
                      action="store_true", dest="release_to_candidates_dir",
                      help="Copy files to $product/$nightly_dir/$version-candidates/build$build_number")
    parser.add_option("-t", "--release-to-tinderbox-builds",
                      action="store_true", dest="release_to_tinderbox_builds",
                      help="Copy files to $product/tinderbox-builds/$tinderbox_builds_dir")
    parser.add_option("--release-to-tinderbox-dated-builds",
                      action="store_true", dest="release_to_dated_tinderbox_builds",
                      help="Copy files to $product/tinderbox-builds/$tinderbox_builds_dir/$timestamp")
    parser.add_option("--release-to-shadow-central-builds",
                      action="store_true", dest="release_to_shadow_central_builds",
                      help="Copy files to $product/shadow-central-builds/$tinderbox_builds_dir/$timestamp")
    parser.add_option("--release-to-tryserver-builds",
                      action="store_true", dest="release_to_tryserver_builds",
                      help="Copy files to tryserver-builds/$who-$revision")
    (options, args) = parser.parse_args()
    
    if len(args) < 2:
        print "Error, you must specify a directory and at least one file."
        error = True

    if not options.product:
        print "Error, you must supply the product name."
        error = True

    if options.release_to_latest:
        releaseTo.append(ReleaseToLatest)
        if not options.branch:
            print "Error, you must supply the branch name."
            error = True
    if options.release_to_dated:
        releaseTo.append(ReleaseToDated)
        if not options.branch:
            print "Error, you must supply the branch name."
            error = True
        if not options.buildid:
            print "Error, you must supply the build id."
            error = True
    if options.release_to_candidates_dir:
        releaseTo.append(ReleaseToCandidatesDir)
        if not options.version:
            print "Error, you must supply the version number."
            error = True
        if not options.build_number:
            print "Error, you must supply the build number."
            error = True
    if options.release_to_tinderbox_builds:
        releaseTo.append(ReleaseToTinderboxBuildsOverwrite)
        if not options.tinderbox_builds_dir:
            print "Error, you must supply the tinderbox builds dir."
            error = True
    if options.release_to_dated_tinderbox_builds:
        releaseTo.append(ReleaseToTinderboxBuilds)
        if not options.tinderbox_builds_dir:
            print "Error, you must supply the tinderbox builds dir."
            error = True
        if not options.buildid:
            print "Error, you must supply the build id."
            error = True
    if options.release_to_shadow_central_builds:
        releaseTo.append(ReleaseToShadowCentralBuilds)
        if not options.tinderbox_builds_dir:
            print "Error, you must supply the tinderbox builds dir."
            error = True
        if not options.buildid:
            print "Error, you must supply the build id."
            error = True
    if options.release_to_tryserver_builds:
        releaseTo.append(ReleaseToTryserverBuilds)
        if not options.who:
            print "Error, must supply who"
            error = True
        if not options.revision:
            print "Error, you must supply the revision"
            error = True
        if not options.builddir:
            print "Error, you must supply the builddir"
            error = True
    if len(releaseTo) == 0:
        print "Error, you must pass a --release-to option!"
        error = True
    
    if error:
        sys.exit(1)
    
    NIGHTLY_PATH = NIGHTLY_PATH % {'product': options.product,
                                   'nightly_dir': options.nightly_dir}
    upload_dir = os.path.abspath(args[0])
    files = args[1:]
    if not os.path.isdir(upload_dir):
        print "Error, %s is not a directory!" % upload_dir
        sys.exit(1)
    for f in files:
        f = os.path.abspath(f)
        if not os.path.isfile(f):
            print "Error, %s is not a file!" % f
            sys.exit(1)
    
    for func in releaseTo:
        func(options, upload_dir, files)
