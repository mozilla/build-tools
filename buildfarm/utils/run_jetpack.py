#!/usr/bin/python
""" Usage: %prog platform [sdk_location] [tarball_url] [ftp_url] [extension]

Script to pull down the latest jetpack sdk tarball, unpack it, and run its tests against the 
executable of whatever valid platform is passed.
"""
import os, sys, urllib, shutil
from optparse import OptionParser

SDK_TARBALL="addonsdk.tar.bz2"
POLLER_DIR="addonsdk-poller"
SDK_DIR="jetpack"

if __name__ == '__main__':
    is_poller = False
    untar_args=''
    parser = OptionParser(usage=__doc__)
    parser.add_option("-e", "--extension", dest="ext", default="",
                      help="Extension to match in the builds directory for downloading the build")
    parser.add_option("-f", "--ftp-url", dest="ftp_url", default="",
                      help="Url for ftp latest-builds directory where the build to download lives")
    parser.add_option("-s", "--sdk-location", dest="sdk_location", default='jetpack-location.txt',
                      help="Text file or url to use to download the current addonsdk tarball")
    parser.add_option("-p", "--platform", dest="platform",
                      help="Platform of the build to download and to test")
    parser.add_option("-t", "--tarball-url", dest="tarball_url", default="",
                      help="Url to download the jetpack tarball from")

    (options, args) = parser.parse_args()

    # Handling method of running tests (branch checkin vs. poller on addon-sdk repo)
    if options.ftp_url == "":
        # Branch change triggered test suite
        # 'jetpack' dir must exist the build's tests package
        if os.path.exists("./%s" % SDK_DIR):
            os.chdir(SDK_DIR)
            if ".txt" in options.sdk_location:
                f = open(options.sdk_location, 'r')
                sdk_url = f.readline()
                print "SDK_URL: %s" % sdk_url
                f.close()
            else:
                sdk_url = options.sdk_location
            os.chdir('..')
            basepath = os.getcwd()
        else:
            print("No jetpack directory present!  Cannot run test suite.")
            sys.exit(1)
    elif options.ftp_url != "" and options.ext != "" and options.tarball_url != "":
        # Addonsdk checkin triggered
        is_poller = True
        # Clobber previous run
        if os.path.exists("./%s" % POLLER_DIR):
            shutil.rmtree(POLLER_DIR)
        # Make a new workdir
        os.mkdir(POLLER_DIR)
        os.chdir(POLLER_DIR)
        basepath = os.getcwd()
        sdk_url = options.tarball_url
        # Download the build from the ftp_url provided
        urls = urllib.urlopen("%s" % options.ftp_url)
        filenames = urls.read().splitlines()
        executables = []
        for filename in filenames:
            if options.ext in filename:
                executables.append(filename.split(" ")[-1])
        # Only grab the most recent build (in case there's more than one in the dir)
        exe = sorted(executables, reverse=True)[0]
        print "EXE_URL: %s/%s" % (options.ftp_url, exe)
        urllib.urlretrieve("%s/%s" % (options.ftp_url, exe), exe)
    else:
        parser.error("Incorrect number of arguments")
        sys.exit(1)

    # Custom paths/args for each platform's executable
    if options.platform in ('linux', 'linux64', 'fedora', 'fedora64'):
        app_path = "%s/firefox/firefox" % basepath
        poller_cmd = 'tar -xjvf *%s' % options.ext
    elif options.platform in ('macosx', 'macosx64', 'leopard', 'snowleopard'):
        poller_cmd = '../scripts/buildfarm/utils/installdmg.sh *%s' % options.ext
    elif options.platform in ('win32', 'win7', 'win764', 'w764', 'xp'):
        app_path = "%s/firefox/firefox.exe" % basepath
        # The --exclude=*.app is here to avoid extracting a symlink on win32 that is only
        # relevant to OS X. It would be nice if we could just tell tar to ignore symlinks...
        untar_args = "--exclude=*.app"
        poller_cmd = 'unzip -o *%s' % options.ext
    else:
        print "%s is not a valid platform." % options.platform
        sys.exit(1)

    # Download/untar sdk tarball as SDK_TARBALL
    print "SDK_URL: %s" % sdk_url
    urllib.urlretrieve(sdk_url, SDK_TARBALL)
    os.system('tar -xvf %s %s' % (SDK_TARBALL, untar_args))

    # Unpack/mount/unzip the executables in addonsdk checkin triggered runs
    if is_poller:
        os.system(poller_cmd)

    # Find the sdk dir and Mac .app file to run tests with 
    # Must happen after poller_cmd is run or Mac has no executable yet in addonsdk checkin runs
    dirs = os.listdir('.')
    for dir in dirs:
        if 'addon-sdk' in dir:
            sdkdir = os.path.abspath(dir)
            print "SDKDIR: %s" % sdkdir
        if options.platform in ('macosx', 'macosx64', 'leopard', 'snowleopard'):
            if '.app' in dir:
                app_path = os.path.abspath(dir)
                print "APP_PATH: %s" % app_path

    if not os.path.exists(app_path):
        print "The APP_PATH \"%s\" does not exist" % app_path
        sys.exit(1)

    # Run it!
    if sdkdir:
        os.chdir(sdkdir)
        os.system('python bin/cfx --verbose testall -a firefox -b %s' % app_path)
    else:
        print "SDK_DIR is either missing or invalid."
        sys.exit(1)
