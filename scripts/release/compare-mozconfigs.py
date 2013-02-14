#!/usr/bin/python
import logging
from os import path
import site
import sys

site.addsitedir(path.join(path.dirname(__file__), "../../lib/python"))

from release.sanity import verify_mozconfigs

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()

    parser.add_option('--branch', dest='branch')
    parser.add_option('--revision', dest='revision')
    parser.add_option('--hghost', dest='hghost', default='hg.mozilla.org')
    parser.add_option('--product', dest='product')
    parser.add_option('--whitelist', dest='whitelist')
    options, args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    mozconfigs = {}
    for arg in args:
        platform, mozconfig = arg.split(',')
        mozconfigs[platform] = mozconfig

    passed = verify_mozconfigs(options.branch, options.revision, options.hghost,
                               options.product, mozconfigs, options.whitelist)

    if passed:
        logging.info('Mozconfig check passed!')
    else:
        logging.error('Mozconfig check failed!')
    sys.exit(not passed)
