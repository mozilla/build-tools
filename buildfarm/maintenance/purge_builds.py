#!/usr/bin/env python
# Written for Mozilla by Chris AtLee <catlee@mozilla.com> 2008
"""Delete old buildbot builds to make room for the current build.

%prog [options] base_dir

base_dir is the root of the directory tree you want to delete builds
from.

Sub-directories of base_dir will be deleted, in order from oldest to newest,
until the specified amount of space is free.

example:
    python %prog -s 6 /builds/moz2_slave
"""

import os, shutil, re, sys

if sys.platform == 'win32':
    # os.statvfs doesn't work on Windows
    import win32file
    def freespace(p):
        secsPerClus, bytesPerSec, nFreeClus, totClus = win32file.GetDiskFreeSpace(p)
        return secsPerClus * bytesPerSec * nFreeClus
else:
    def freespace(p):
        "Returns the number of bytes free under directory `p`"
        r = os.statvfs(p)
        return r.f_frsize * r.f_bavail

def mtime_sort(p1, p2):
    "sorting function for sorting a list of paths by mtime"
    return cmp(os.path.getmtime(p1), os.path.getmtime(p2))

def rmdirRecursive(dir):
    """This is a replacement for shutil.rmtree that works better under
    windows. Thanks to Bear at the OSAF for the code.
    (Borrowed from buildbot.slave.commands)"""
    if not os.path.exists(dir):
        # This handles broken links
        if os.path.islink(dir):
            os.remove(dir)
        return

    if os.path.islink(dir):
        os.remove(dir)
        return

    # Verify the directory is read/write/execute for the current user
    os.chmod(dir, 0700)

    for name in os.listdir(dir):
        full_name = os.path.join(dir, name)
        # on Windows, if we don't have write permission we can't remove
        # the file/directory either, so turn that on
        if os.name == 'nt':
            if not os.access(full_name, os.W_OK):
                # I think this is now redundant, but I don't have an NT
                # machine to test on, so I'm going to leave it in place
                # -warner
                os.chmod(full_name, 0600)

        if os.path.isdir(full_name):
            rmdirRecursive(full_name)
        else:
            # Don't try to chmod links
            if not os.path.islink(full_name):
                os.chmod(full_name, 0700)
            os.remove(full_name)
    os.rmdir(dir)

def purge(base_dir, gigs, ignore, dry_run=False):
    """Delete directories under `base_dir` until `gigs` GB are free

    Will not delete directories listed in the ignore list."""
    gigs *= 1024 * 1024 * 1024

    if freespace(base_dir) >= gigs:
        return

    dirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d not in ignore]
    dirs.sort(mtime_sort)
    while dirs and freespace(base_dir) < gigs:
        d = dirs.pop(0)
        print "Deleting", d
        if not dry_run:
            rmdirRecursive(d)

if __name__ == '__main__':
    import sys
    from optparse import OptionParser

    parser = OptionParser(usage=__doc__)
    parser.set_defaults(size=5, skip=[], no_presets=False, dry_run=False)

    parser.add_option('-s', '--size',
            help='free space required (in GB, default 5)', dest='size',
            type='float')

    parser.add_option('-n', '--not', help='do not delete this directory',
            action='append', dest='skip')

    parser.add_option('', '--dry-run', action='store_true',
            dest='dry_run',
            help='''do not delete anything, just print out what would be
deleted.  note that since no directories are deleted, if the amount of free
disk space in base_dir is less than the required size, then ALL directories
will be listed in the order in which they would be deleted.''')

    options, args = parser.parse_args()

    if len(args) != 1:
        parser.error("Must specify exactly one base_dir")
        sys.exit(1)

    purge(args[0], options.size, options.skip, options.dry_run)
    print "%1.2f GB of space available" % (freespace(args[0])/(1024*1024*1024.0))
