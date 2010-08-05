#!/usr/bin/env python
# Created by Lukas Blakk on 2010-07-22
"""talos_sendchange.py tryserverDir

example usage:
    python talos_sendchange.py mak77@bonardo.net-04da41d5f2ce

This script creates and sends sendchanges for each of the
PLATFORMS to each of the TEST_MASTERS"""

import sys, os
from ftplib import FTP

TEST_MASTERS = ['production-master01.build.mozilla.org:9009']
PLATFORMS = ['linux', 'linux64', 'macosx', 'macosx64', 'win32']
STAGE_BASE_PATH = '/pub/mozilla.org/firefox/tryserver-builds/%(email)s-%(changeset)s/tryserver-%(platform)s/'

if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) == 1:
        for master in TEST_MASTERS:
            email, dummy, changeset = args[0].rpartition('-')
            ftp = FTP('ftp.mozilla.org')
            ftp.login()

            for platform in PLATFORMS:
                tryserverUrlPath = STAGE_BASE_PATH % {'email': email, 
                                                      'changeset': changeset, 
                                                      'platform': platform}
                filelist = ftp.nlst(tryserverUrlPath)

                for f in filelist:
                    for suffix in ('.tar.bz2', '.win32.zip', '.dmg'):
                        if f.split(' ')[-1].endswith(suffix):
                            sendchange = "buildbot sendchange --master %(master)s " \
                                         "--branch tryserver-%(platform)s-talos --revision %(changeset)s " \
                                         "--user %(email)s http://stage.mozilla.org%(f)s" \
                                         % {'master': master,
                                            'platform': platform,
                                            'changeset': changeset,
                                            'email': email,
                                            'f': f}
                            print "Sending %s:%s" % (platform,master) 
                            os.system(sendchange)
                            print sendchange
            ftp.quit()
    else:
       print "Usage: python talos_sendchange.py email-changeset"
