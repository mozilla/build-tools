#!/usr/bin/python

# MOZILLA DEPLOYMENT NOTES
# - This file is distributed to all buildslaves by Puppet, placed at
#   /usr/local/bin/runslave.py on POSIX systems (linux, darwin) and
#   C:\runslave.py on Windows systems
# - It lives in build/tools at buildbot-helpers/startup/runslave.py

import sys
import time
import re
import os
import traceback
import subprocess
import textwrap
import urllib2

class BuildbotTac:
    def __init__(self, options):
        self.options = options
        self.filename = os.path.join(options.basedir, "buildbot.tac")

    def exists(self):
        return os.path.exists(self.filename)

    def download(self):
        url = self.options.allocator_url
        slavename = self.options.slavename
        slavename = slavename.split('.', 1)[0]

        # create a full URL based on the slave name
        full_url = url.replace('SLAVE', slavename)

        try:
            page = urllib2.urlopen(full_url)
            page = page.read()

            # check that it's (likely to be) valid
            if 'AUTOMATICALLY GENERATED - DO NOT MODIFY' not in page:
                print "downloaded page did not contain validity-check string"
                return False

            # tuck it away in buildbot.tac
            if self.options.verbose:
                print "writing", self.filename
            tmpfile = '%s.tmp' % self.filename
            f = open(tmpfile, "w")
            f.write(page)
            os.rename(tmpfile, self.filename)
            return True
        except:
            print "error while fetching ", full_url
            if self.options.verbose:
                traceback.print_exc()
            # oh noes!  No worries, we'll just use the existing .tac file
            return False

    def run(self):
        assert self.exists()
        sys.exit(subprocess.call([self.options.buildslave_cmd, 'start', self.options.basedir]))

default_allocator_url = "http://build.mozilla.org/buildbot/tac/SLAVE"
if __name__ == '__main__':
    from optparse import OptionParser
    import socket

    parser = OptionParser(usage=textwrap.dedent("""\
        usage:
            %%prog [--verbose] [--allocator-url URL] [--buildslave-cmd CMD]
                        [--basedir BASEDIR] [--slavename SLAVE]
                        [--no-start]

        Attempt to download a .tac file from the allocator, or use a locally cached
        version if an error occurs.  The slave name is used to determine the basedir,
        and is calculated from gethostname() if not given on the command line.

        The slave name, if not specified, is determined via gethostname().

        The basedir, if not specified, is calculated from the slave name; see the
        code for details.

        So long as a file named DO_NOT_START exists in the basedir, the script will
        block and not start the slave.

        The allocator URL defaults to
          %(default_allocator_url)s
        The URL will have the string 'SLAVE' replaced with the unqualified
        slavename.  The resulting page should be the plain-text .tac file to be
        written to disk.  It must contain the string
          AUTOMATICALLY GENERATED - DO NOT MODIFY
        (as a safety check that it's valid).

        Once the .tac file is set up, this invokes 'CMD start BASEDIR'.  CMD is
        from --buildslave-cmd, and is calculated based on the slave name if not
        specified.  The buildslave is not started if --no-start is provided.
    """ % dict(default_allocator_url=default_allocator_url)))
    parser.add_option("-a", "--allocator-url", action="store", dest="allocator_url")
    parser.add_option("-c", "--buildslave-cmd", action="store", dest="buildslave_cmd")
    parser.add_option("-d", "--basedir", action="store", dest="basedir")
    parser.add_option("-n", "--slavename", action="store", dest="slavename")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose")
    parser.add_option(      "--no-start", action="store_true", dest="no_start")
    parser.set_defaults(allocator_url=default_allocator_url)

    (options, args) = parser.parse_args()

    # apply some defaults
    if not options.slavename:
        options.slavename = socket.gethostname().split('.')[0]
    def slave_matches(*parts):
        "True if any of PARTS appears in options.slavename"
        for part in parts:
            if part in options.slavename:
                return True
        return False

    if not options.basedir:
        if slave_matches('slave'):
            if slave_matches('linux', 'darwin'):
                options.basedir = '/builds/slave'
            elif slave_matches('win', 'w32'):
                options.basedir = r'e:\builds\moz2_slave'
        elif slave_matches('talos', '-try', 'r3'):
            if slave_matches('linux', 'ubuntu', 'fed'):
                options.basedir = '/home/cltbld/talos-slave'
            elif slave_matches('tiger', 'leopard', 'snow'):
                options.basedir = '/Users/cltbld/talos-slave'
            elif slave_matches('xp', 'w7'):
                options.basedir = r'c:\talos-slave'

        if not options.basedir:
            parser.error("could not determine basedir")

    if not os.path.exists(options.basedir):
        parser.error("basedir '%s' does not exist" % options.basedir)

    # check for DO_NOT_START
    do_not_start = os.path.join(options.basedir, "DO_NOT_START")
    while os.path.exists(do_not_start):
        if options.verbose:
            print "waiting until '%s' goes away" % do_not_start
        time.sleep(10)

    if not options.buildslave_cmd:
        if slave_matches('linux'):
            options.buildslave_cmd = '/tools/buildbot/bin/buildbot'
        if slave_matches('fed'):
            options.buildslave_cmd = '/tools/buildbot-0.8.0/bin/buildbot'

        if not options.buildslave_cmd:
            parser.error("could not determine buildslave command")

    # set up the .tac file
    tac = BuildbotTac(options)
    ok = tac.download()
    if not ok and not tac.exists():
        print >>sys.stderr, "could not reach allocator and no existing buildbot.tac; failed!"

    if not options.no_start:
        tac.run()
