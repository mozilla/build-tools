#!/usr/bin/python
import os
import optparse

from image_manip import *

if __name__=='__main__':
    parser = optparse.OptionParser('Usage: %prog -r rootdir -o outdir')
    parser.add_option('-r', '--root', action='store', dest='rootdir',
                      help='Specify the root directory of the new image')
    parser.add_option('-o', '--output', action='store', dest='output',
                      help='Specify the output file. Use the basename of the file \
                      (e.g. do not include .ubi, .ubifs, .jffs2)')
    parser.add_option('--mkfs-ubifs', action='store', dest='mkfs_ubifs', default='./mkfs.ubifs',
                      help='specify a non-default mkfs.ubifs')
    parser.add_option('--ubinize', action='store', dest='ubinize', default='./ubinize',
                      help='specify a non-default ubinize')
    parser.add_option('--rsync', action='store', dest='rsync', default='rsync',
                      help='specify a non-default rsync application')
    (options, args) = parser.parse_args()

    try:
        assert os.getuid() == 0, 'This script must be run as root'
        assert options.rootdir and options.output, 'You must specify a root directory and output file'
        for ending in ['.jffs2', '.ubifs', '.ubi']:
            assert not options.output.endswith(ending), 'You should not use the "%" file ending' % ending
        rsync = path_lookup(options.rsync[:])
        ubinize = path_lookup(options.ubinize[:])
        mkfs_ubifs = path_lookup(options.mkfs_ubifs[:])
        assert os.path.exists(rsync), 'Could not find %s' % rsync
        assert os.path.exists(ubinize), 'Could not find %s' % ubinize
        assert os.path.exists(mkfs_ubifs), 'Could not find %s' % mkfs_ubifs
        assert os.path.exists(options.rootdir), 'Root directory is missing (%s)' % options.rootdir
        assert os.path.isdir(options.rootdir), 'Root directory needs to be a directory (%s)' % options.rootdir
    except AssertionError, ae:
        print 'ERROR: %s' % ae.args[0]
        parser.print_help()
        exit(1)
    try:
        assert not os.path.exists('%s.ubifs' % options.output), 'This script will not over-write an output file (%s.ubifs)' % options.output
        assert not os.path.exists('%s.ubi' % options.output), 'This script will not over-write an output file (%s.ubi)' % options.output
        generate_ubifile(options.rootdir, options.output, rsync, mkfs_ubifs, ubinize)
    except AssertionError, ae:
        print 'ERROR: %s' % ae.args[0]
        if os.path.exists(options.output):
            print '\n\nWARNING: The files in "%s" are likely busted!' % options.output
        exit(1)

    print 'Success!'

