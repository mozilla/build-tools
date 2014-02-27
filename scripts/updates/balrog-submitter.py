#!/usr/bin/env python

import json
import os
import site
import logging
import sys


site.addsitedir(os.path.join(os.path.dirname(__file__), "../../lib/python"))

from balrog.submitter.cli import NightlySubmitter, ReleaseSubmitter


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-p", "--build-properties", dest="build_properties")
    parser.add_option("-a", "--api-root", dest="api_root")
    parser.add_option("-c", "--credentials-file", dest="credentials_file")
    parser.add_option("-u", "--username", dest="username", default="ffxbld")
    parser.add_option("-t", "--type", dest="type_", help="nightly or release", default="nightly")
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
    auth = (options.username, credentials['balrog_credentials'][options.username])
    fp = open(options.build_properties)
    bp = json.load(fp)
    fp.close()
    props = bp['properties']
    locale = props.get('locale', 'en-US')
    extVersion = props.get('extVersion', props['appVersion'])
    if options.type_ == "nightly":
        partialKwargs = {
            'partialMarSize': props.get('partialMarSize')
        }
        if partialKwargs['partialMarSize']:
            partialKwargs['partialMarHash'] = props['partialMarHash']
            partialKwargs['partialMarUrl'] = props['partialMarUrl']
            partialKwargs['previous_buildid'] = props['previous_buildid']
        submitter = NightlySubmitter(options.api_root, auth, options.dummy)
        submitter.run(props['platform'], props['buildid'], props['appName'],
            props['branch'], props['appVersion'], locale, props['hashType'],
            extVersion, props['completeMarSize'], props['completeMarHash'],
            props['completeMarUrl'], **partialKwargs)
    elif options.type_ == "release":
        submitter = ReleaseSubmitter(options.api_root, auth, options.dummy)
        submitter.run(props['platform'], props['appName'], props['appVersion'],
            props['version'], props['build_number'], locale,
            props['hashType'], extVersion, props['buildid'],
            props['completeMarSize'], props['completeMarHash'])
    else:
        parser.error("Invalid value for --type")
