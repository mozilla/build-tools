#!/usr/bin/python
""" Usage: %prog platform [sdk_location] [tarball_url] [ftp_url] [extension]

Script to pull down the latest jetpack sdk tarball, unpack it, and run its tests against the 
executable of whatever valid platform is passed.
"""
import os, sys, urllib, shutil, re, traceback
import logging, subprocess
from datetime import datetime, timedelta
from optparse import OptionParser

SDK_TARBALL="addonsdk.tar.bz2"
POLLER_DIR="addonsdk-poller"
SDK_DIR="jetpack"

PLATFORMS = {'leopard': 'macosx64',
             'snowleopard': 'macosx64',
             'lion': 'macosx64',
             'xp': 'win32',
             'win7': 'win32',
             'w764': 'win64',
             'fedora': 'linux',
             'fedora64': 'linux64',
             }
             

log = logging.getLogger()
# copied runCommand from tools/sut_tools/sut_lib.py
def runCommand(cmd, env=None, logEcho=True):
    """Execute the given command.
    Sends to the logger all stdout and stderr output.
    """
    log.debug('calling [%s]' % ' '.join(cmd))

    o = []
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    try:
        for item in p.stdout:
            o.append(item[:-1])
            if logEcho:
                log.debug(item[:-1])
        p.wait()
    except KeyboardInterrupt:
        p.kill()
        p.wait()

    return p, o

def emphasizeFailureText(text):
    return '<em class="testfail">%s</em>' % text

def summarizeJetpackTestLog(name, log):
    infoRe = re.compile(r"(\d+) of (\d+) tests passed")
    successCount = 0
    failCount = 0
    totalCount = 0
    summary=""
    for line in log:
        m = infoRe.match(line)
        if m:
            successCount += int(m.group(1))
            totalCount += int(m.group(2))
    failCount = int(totalCount - successCount)
    # Handle failCount.
    failCountStr = str(failCount)
    if failCount > 0:
        failCountStr = emphasizeFailureText(failCountStr)
    # Format the counts
    summary = "%d/%d" % (totalCount, failCount)
    # Return the summary.
    return "TinderboxPrint:%s<br />%s\n" % (name, summary)

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
    parser.add_option("-b", "--branch", dest="branch", default="",
                      help="The branch this test is pulling an installer to run against")

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
        # need this as long as we support 32bit macosx debug builds
        if options.platform == 'leopard' and options.ftp_url.endswith('debug'):
            platform = 'macosx'
        else:
            platform = PLATFORMS[options.platform]
        branch = options.branch
        ftp_url = options.ftp_url % locals()
        pat = re.compile('firefox.*%s$' % options.ext)
        urls = urllib.urlopen("%s" % ftp_url)
        lines = urls.read().splitlines()
        # initialize an old datetime to compare the current FTP dirs against to find newest
        most_recent = datetime.now()-timedelta(days=30)
        directory = None

        # let's use the datetime to locate the FTP directory to search for executable
        for line in lines:
            if line.startswith('d'):
                parts = line.split(" ")
                # make sure we have a modified time for this dir
                if ":" in parts[-2]:
                    time = " ".join([str(datetime.now().year), parts[-4], parts[-3], parts[-2]]) 
                    dir_time = datetime.strptime(time, "%Y %b %d %H:%M")
                    if dir_time > most_recent:
                        most_recent = dir_time
                        directory = parts[-1]

        # Now get the executable for this platform
        if directory == None:
            print "Error, no directory set to check for executables"
            sys.exit(1)
        urls = urllib.urlopen("%s/%s" % (ftp_url, directory))
        filenames = urls.read().splitlines()
        executables = []
        for filename in filenames:
            f = filename.split(" ")[-1]
            if pat.match(f):
                executables.append(f)
        # Only grab the most recent build (in case there's more than one in the dir)
        if len(executables) > 0:
            exe = sorted(executables, reverse=True)[0]
        else:
            print "Error: missing Firefox executable"
            sys.exit(1)
        info_file = exe.replace(options.ext, "%s.txt" % options.ext.split('.')[0])
        # Now get the branch revision
        for filename in filenames:
            if info_file in filename:
                info = filename.split(" ")[-1]
                urllib.urlretrieve("%s/%s/%s" % (ftp_url, directory, info), info)
                f = open(info, 'r')
                for line in f.readlines():
                    if "hg.mozilla.org" in line:
                        branch_rev = line.split('/')[-1].strip()
                        branch = line.split('/')[-3].strip()
                        print "TinderboxPrint: <a href=\"http://hg.mozilla.org/%(branch)s/rev/%(branch_rev)s\">%(branch)s-rev:%(branch_rev)s</a>\n" % locals()
                f.close()
        print "EXE_URL: %s/%s/%s" % (ftp_url, directory, exe)
        # Download the build
        urllib.urlretrieve("%s/%s/%s" % (ftp_url, directory, exe), exe)
    else:
        parser.error("Incorrect number of arguments")
        sys.exit(1)

    # Custom paths/args for each platform's executable
    if options.platform in ('linux', 'linux64', 'fedora', 'fedora64'):
        app_path = "%s/firefox/firefox" % basepath
        poller_cmd = 'tar -xjvf *%s' % options.ext
    elif options.platform in ('macosx', 'macosx64', 'leopard', 'snowleopard', 'lion'):
        poller_cmd = '../scripts/buildfarm/utils/installdmg.sh *.dmg'
    elif options.platform in ('win32', 'win7', 'win64', 'win764', 'w764', 'xp'):
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
    try:
        urllib.urlretrieve(sdk_url, SDK_TARBALL)
    except:
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)
    os.system('tar -xvf %s %s' % (SDK_TARBALL, untar_args))

    # Unpack/mount/unzip the executables in addonsdk checkin triggered runs
    if is_poller:
        os.system(poller_cmd)

    # Find the sdk dir and Mac .app file to run tests with 
    # Must happen after poller_cmd is run or Mac has no executable yet in addonsdk checkin runs
    dirs = os.listdir('.')
    for dir in dirs:
        if 'addon-sdk' in dir:
            sdk_rev = dir.split('-')[2]
            print "TinderboxPrint: <a href=\"http://hg.mozilla.org/projects/addon-sdk/rev/%(sdk_rev)s\">sdk-rev:%(sdk_rev)s</a>\n" % locals()
            sdkdir = os.path.abspath(dir)
            print "SDKDIR: %s" % sdkdir
        if options.platform in ('macosx', 'macosx64', 'leopard', 'snowleopard', 'lion'):
            if '.app' in dir:
                app_path = os.path.abspath(dir)
                print "APP_PATH: %s" % app_path

    if not os.path.exists(app_path):
        print "The APP_PATH \"%s\" does not exist" % app_path
        sys.exit(1)

    # Run it!
    if sdkdir:
        os.chdir(sdkdir)
        args = ['python', 'bin/cfx', '--verbose', 'testall', '-a', 'firefox', '-b', app_path]
        process, output = runCommand(args)
        print '\n'.join(output)
        if is_poller:
            print summarizeJetpackTestLog("Jetpack",output)
        sys.exit(process.returncode)
    else:
        print "SDK_DIR is either missing or invalid."
        sys.exit(1)
