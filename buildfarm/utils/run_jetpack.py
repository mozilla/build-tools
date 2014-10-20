#!/usr/bin/python
""" Usage: %prog platform [sdk_location] [tarball_url] [ftp_url] [extension]

Script to pull down the latest jetpack sdk tarball, unpack it, and run its tests against the
executable of whatever valid platform is passed.
"""
import os
import sys
import urllib
import shutil
import re
import traceback
import time
import logging
import subprocess
import mozdownload
from optparse import OptionParser

SDK_TARBALL = "addonsdk.tar.bz2"
POLLER_DIR = "addonsdk-poller"
SDK_DIR = "jetpack"

PLATFORM_FRAGMENTS = {
    'snowleopard': 'mac64',
    'lion': 'mac64',
    'mountainlion': 'mac64',
    'mavericks': 'mac64',
    'xp-ix': 'win32',
    'win7-ix': 'win32',
    'win8': 'win32',
    'w764': 'win64',
    'ubuntu32': 'linux',
    'ubuntu64': 'linux64',
    'ubuntu32_vm': 'linux',
    'ubuntu64_vm': 'linux64',
    'ubuntu64-asan_vm': 'linux64'
}

log = logging.getLogger()


# copied runCommand from tools/sut_tools/sut_lib.py
def runCommand(cmd, env=None, logEcho=True):
    """Execute the given command.
    Sends to the logger all stdout and stderr output.
    """
    log.debug('calling [%s]' % ' '.join(cmd))

    o = []
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)

    try:
        for item in p.stdout:
            o.append(item[:-1])
            print item[:-1]
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
    summary = ""
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
    return "TinderboxPrint:%s<br/>%s\n" % (name, summary)

if __name__ == '__main__':
    is_poller = False
    untar_args = ''
    parser = OptionParser(usage=__doc__)
    parser.add_option("-e", "--extension", dest="ext", default="",
                      help="Extension to match in the builds directory for downloading the build")
    parser.add_option(
        "-s", "--sdk-location", dest="sdk_location", default='jetpack-location.txt',
        help="Text file or url to use to download the current addonsdk tarball")
    parser.add_option("-p", "--platform", dest="platform",
                      help="Platform of the build to download and to test")
    parser.add_option("-t", "--tarball-url", dest="tarball_url", default="",
                      help="Url to download the jetpack tarball from")
    parser.add_option("-b", "--branch", dest="branch", default="",
                      help="The branch this test is pulling an installer to run against")

    (options, args) = parser.parse_args()

    if options.ext != "" and options.tarball_url != "":
        # Addonsdk checkin triggered
        is_poller = True

        # Clobber previous run
        # First try to delete n-2 run which failed to be removed
        if os.path.exists("./" + POLLER_DIR + ".deleteme"):
            try:
                shutil.rmtree(POLLER_DIR + ".deleteme")
                time.sleep(1)
            except EnvironmentError:
                print("Unable to delete n-2 run folder")
        # Then try to delete n-1 test run
        if os.path.exists("./%s" % POLLER_DIR):
            try:
                shutil.rmtree(POLLER_DIR)
            except OSError, e:
                print("Unable to delete n-1 run folder")
                time.sleep(1)
                # Rename it and try to delete it on next run
                os.rename(POLLER_DIR, POLLER_DIR + ".deleteme")

        # Make a new workdir
        os.mkdir(POLLER_DIR)
        os.chdir(POLLER_DIR)
        basepath = os.getcwd()
        sdk_url = options.tarball_url
        branch = options.branch


        nightly = mozdownload.TinderboxScraper(
                                     directory=basepath,
                                     version=None,
                                     branch=branch,
                                     platform=PLATFORM_FRAGMENTS[options.platform])
        nightly.download();
    else:
        parser.error("Incorrect number of arguments")
        sys.exit(4)

    # Custom paths/args for each platform's executable
    if options.platform in ('linux', 'linux64', 'ubuntu32', 'ubuntu64',
                            'ubuntu32_vm', 'ubuntu64_vm', 'ubuntu64-asan_vm'):
        app_path = "%s/firefox/firefox" % basepath
        poller_cmd = 'tar -xjvf *%s' % options.ext
    elif options.platform in ('macosx', 'macosx64', 'snowleopard', 'mountainlion', 'mavericks'):
        poller_cmd = '../scripts/buildfarm/utils/installdmg.sh *.dmg'
    elif options.platform in ('win32', 'win7-ix', 'win8', 'win64', 'xp-ix'):
        app_path = "%s/firefox/firefox.exe" % basepath
        # The --exclude=*.app is here to avoid extracting a symlink on win32 that is only
        # relevant to OS X. It would be nice if we could just tell tar to
        # ignore symlinks...
        untar_args = "--exclude=*.app"
        poller_cmd = 'unzip -o *%s' % options.ext
    else:
        print "%s is not a valid platform." % options.platform
        sys.exit(4)

    # Download/untar sdk tarball as SDK_TARBALL
    print "SDK_URL: %s" % sdk_url
    try:
        urllib.urlretrieve(sdk_url, SDK_TARBALL)
    except EnvironmentError:
        traceback.print_exc(file=sys.stdout)
        sys.exit(4)
    os.system('tar -xvf %s %s' % (SDK_TARBALL, untar_args))

    # Unpack/mount/unzip the executables in addonsdk checkin triggered runs
    if is_poller:
        os.system(poller_cmd)

    # Find the sdk dir and Mac .app file to run tests with
    # Must happen after poller_cmd is run or Mac has no executable yet in
    # addonsdk checkin runs
    dirs = os.listdir('.')
    for d in dirs:
        if 'addon-sdk' in d:
            sdk_rev = d.split('-')[2]
            print "TinderboxPrint: <a href=\"https://hg.mozilla.org/projects/addon-sdk/rev/%(sdk_rev)s\">sdk-rev:%(sdk_rev)s</a>\n" % locals()
            sdkdir = os.path.abspath(d)
            print "SDKDIR: %s" % sdkdir
        if options.platform in ('macosx', 'macosx64', 'snowleopard', 'lion', 'mountainlion', 'mavericks'):
            if '.app' in d:
                app_path = os.path.abspath(d)
                print "APP_PATH: %s" % app_path

    if not os.path.exists(app_path):
        print "The APP_PATH \"%s\" does not exist" % app_path
        sys.exit(4)

    # Run it!
    if sdkdir:
        os.chdir(sdkdir)
        args = ['python', 'bin/cfx', '--parseable', '--overload-modules',
                'testall', '-a', 'firefox', '-b', app_path]
        process, output = runCommand(args)
        if is_poller:
            print summarizeJetpackTestLog("Jetpack", output)
        sys.exit(process.returncode)
    else:
        print "SDK_DIR is either missing or invalid."
        sys.exit(4)
