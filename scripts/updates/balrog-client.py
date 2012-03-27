#!/usr/bin/env python

import os
import site
import logging
import sys


site.addsitedir(os.path.join(os.path.dirname(__file__), "../../lib/python"))

from balrog.client.cli import NightlyRunner


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-p", "--build-properties", dest="build_properties")
    parser.add_option("-a", "--api-root", dest="api_root")
    parser.add_option("-c", "--credentials-file", dest="credentials_file")
    parser.add_option("-d", "--dummy", dest="dummy", action="store_true",
                      help="Add '-dummy' suffix to branch name")
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true")
    options, args = parser.parse_args()

    logging_level = logging.INFO
    if options.verbose:
        logging_level = logging.DEBUG
    logging.basicConfig(stream=sys.stdout, level=logging_level,
                        format="%(message)s")

    credentials = {}
    execfile(options.credentials_file, credentials)
    auth = (credentials['balrog_username'], credentials['balrog_password'])
    runner = NightlyRunner(options.build_properties, options.api_root, auth,
                    options.dummy)
    runner.run()
