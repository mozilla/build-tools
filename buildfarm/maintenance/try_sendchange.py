#!/usr/bin/env python
# Created by Lukas Blakk on 2010-08-25
"""try_sendchange.py tryserverDir args

example usage:
    python try_sendchange.py anygregor@gmail.com-2708a2e2b5c0 --build o --p all --u all --t all

This script creates and sends sendchanges for each of the
platforms/test/talos requested to each of the TEST_MASTERS"""

import sys, os, argparse, re
from ftplib import FTP

TEST_MASTERS = ['production-master01.build.mozilla.org:9009']
PLATFORMS = ['linux', 'linux64', 'macosx', 'macosx64', 'win32']
TRY_BASE_PATH = '/pub/mozilla.org/firefox/tryserver-builds/%(email)s-%(changeset)s/'
PLATFORM_BASE_PATH = '/pub/mozilla.org/firefox/tryserver-builds/%(email)s-%(changeset)s/tryserver-%(platform)s/'

if __name__ == "__main__":
    args = sys.argv[1:]

    parser = argparse.ArgumentParser(description='Accepts command line variables for setting sendchange parameters')

    parser.add_argument('--build',
                        default='do',
                        dest='build',
                        help='accepts the build types requested (default is debug & opt)')
    parser.add_argument('--p',
                        default='all',
                        dest='platforms',
                        help='provide a list of desktop platforms, or specify none (default is all)')
    parser.add_argument('--u',
                        default='none',
                        dest='tests',
                        help='provide a list of unit tests, or specify all (default is none)')
    parser.add_argument('--t',
                        default='all',
                        dest='talos',
                        help='provide a list of talos tests, or specify all (default is all)')

    (options, unknown_args) = parser.parse_known_args(args)

    if options.build == 'do' or options.build == 'od':
        options.build = ['opt', 'debug']
    elif options.build == 'd':
        options.build = ['debug']
    elif options.build == 'o':
        options.build = ['opt']
    else:
        options.build = ['opt']

    if options.platforms == 'all':
        platforms = PLATFORMS
    else:
        options.platforms = options.platforms.split(',')
        platforms = options.platforms

    if len(args) >= 1:
        for master in TEST_MASTERS:
            email, dummy, changeset = args[0].rpartition('-')
            ftp = FTP('ftp.mozilla.org')
            ftp.login()

            tryserverDirPath = TRY_BASE_PATH % {'email': email, 
                                                  'changeset': changeset}
            dirlist = ftp.nlst(tryserverDirPath)

            for dir in dirlist:
              for platform in platforms:
                for buildType in options.build:
                  if buildType == 'debug':
                    platform = "%s-%s" % (platform, buildType)
                  if dir.endswith(platform):
                    tryserverUrlPath = PLATFORM_BASE_PATH % {'email': email, 
                                                          'changeset': changeset, 
                                                          'platform': platform}
                    filelist = ftp.nlst(tryserverUrlPath)
                    packagedTests = None

                    for f in filelist:
                        match = re.search('tests', f)
                        if match:
                            packagedTests = f

                    for f in filelist:
                        for suffix in ('.tar.bz2', '.win32.zip', '.dmg'):
                            #print "DEBUG: file = %s" % f
                            if f.endswith(suffix):
                                path = f

                    if options.talos != 'none' and buildType == 'opt':
                        sendchange = "buildbot sendchange --master %(master)s " \
                                     "--branch tryserver-%(platform)s-talos --revision %(changeset)s " \
                                     "--comment \"try: --t %(talos)s\" " \
                                     "--user %(email)s http://stage.mozilla.org%(path)s " \
                                     % {'master': master,
                                        'platform': platform,
                                        'changeset': changeset,
                                        'talos': options.talos,
                                        'email': email,
                                        'path': path}
                        os.system(sendchange)
                        print "Sendchange for Talos: %s" % sendchange
                    if options.tests != 'none' and packagedTests:
                        sendchange = "buildbot sendchange --master %(master)s " \
                                     "--branch tryserver-%(platform)s-%(buildType)s-unittest" \
                                     "--revision %(changeset)s " \
                                     "--comment \"try: --u %(tests)s\" " \
                                     "--user %(email)s http://stage.mozilla.org%(path)s " \
                                     "http://stage.mozilla.org%(packagedTests)s " \
                                     % {'master': master,
                                        'platform': platform,
                                        'buildType': buildType,
                                        'changeset': changeset,
                                        'tests': options.tests,
                                        'email': email,
                                        'path': path,
                                        'packagedTests': packagedTests}
                        os.system(sendchange)
                        print "Sendchange for Unittests: %s" % sendchange
            ftp.quit()
    else:
       print "Usage: python try_sendchange.py email-changeset [optional parameters]"
