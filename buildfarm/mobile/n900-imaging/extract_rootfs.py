#!/usr/bin/python
import os
import optparse

from image_manip import *

if __name__=='__main__':
    parser = optparse.OptionParser('Usage: %prog [-F fiasco]|[--rootfs ubifile] -o outdir')
    parser.add_option('-F', '--fiasco', action='store', dest='fiasco',
                        help='Fiasco file to extract rootfs from')
    parser.add_option('--flasher', action='store', dest='flasher', default='./flasher-3.5',
                      help='specify which flasher tool to unpack fiasco with')
    parser.add_option('--rootfs', action='store', dest='rootfs',
                        help='file that is the stock root filesystem')
    parser.add_option('-o', '--output', action='store', dest='output',
                      help='name of the base directory for extracted image')
    parser.add_option('-m', '--mtd', action='store', dest='mtd', default='/dev/mtd0',
                      help='manually specify an MTD device node to work with')
    parser.add_option('--rsync', action='store', dest='rsync', default='rsync',
                      help='specify a non-default rsync program')
    (options, args) = parser.parse_args()

    try:
        assert os.getuid() == 0, 'This script must be run as root'
        assert options.fiasco or options.rootfs, 'You must specify either a rootfs or a fiasco file'
        assert not (options.fiasco and options.rootfs), 'You can either specify a fiasco file or a raw-ubifile'
        assert options.output, 'You must specify an output directory'
    except AssertionError, ae:
        print 'ERROR: %s' % ae.args[0]
        parser.print_help()
        exit(1)
    try:
        assert not os.path.exists(options.output), 'I will not overwrite an existing image'
        if options.fiasco:
            tmpdir, ubifile = extract_fiasco(options.fiasco, options.flasher, 'rootfs.jffs2')
            extract_ubifile(ubifile, options.output, options.mtd, options.rsync, tmpdir=tmpdir)
        elif options.ubifile:
            extract_ubifile(options.fiasco, options.output, options.mtd, options.rsync)
    except AssertionError, ae:
        print 'ERROR: %s' % ae.args[0]
        if os.path.exists(options.output):
            print '\n\nWARNING: The files in "%s" are likely busted!' % options.output
        exit(1)

    print 'Success!'

