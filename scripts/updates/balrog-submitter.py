#!/usr/bin/env python

import json
import os
import logging
import sys


# Use explicit version of python-requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "../../lib/python/vendor/requests-0.10.8"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lib/python"))

from balrog.submitter.cli import NightlySubmitterV2, ReleaseSubmitterV2, \
    NightlySubmitterV3, ReleaseSubmitterV3


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-p", "--build-properties", dest="build_properties")
    parser.add_option("-a", "--api-root", dest="api_root")
    parser.add_option("-c", "--credentials-file", dest="credentials_file")
    parser.add_option("-u", "--username", dest="username", default="ffxbld")
    parser.add_option("-t", "--type", dest="type_", help="nightly or release", default="nightly")
    parser.add_option("-s", "--schema", dest="schema_version",
                      help="blob schema version", type="int", default=3)
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

    if options.schema_version not in (2, 3):
        parser.error("Only schema_versions 2 and 3 supported.")
    props = bp['properties']
    locale = props.get('locale', 'en-US')
    extVersion = props.get('extVersion', props['appVersion'])
    if options.type_ == "nightly":
        isOSUpdate = props.get('isOSUpdate', None)
        updateKwargs = {}
        if options.schema_version == 2:
            submitter = NightlySubmitterV2(options.api_root, auth, options.dummy)
            updateKwargs.update({
                'completeMarSize': props['completeMarSize'],
                'completeMarHash': props['completeMarHash'],
                'completeMarUrl': props['completeMarUrl'],
                'partialMarSize': props.get('partialMarSize')
            })
            if updateKwargs['partialMarSize']:
                updateKwargs['partialMarHash'] = props['partialMarHash']
                updateKwargs['partialMarUrl'] = props['partialMarUrl']
                updateKwargs['previous_buildid'] = props['previous_buildid']
        else:
            submitter = NightlySubmitterV3(options.api_root, auth, options.dummy)
            updateKwargs["completeInfo"] = [{
                'size': props['completeMarSize'],
                'hash': props['completeMarHash'],
                'url': props['completeMarUrl'],
            }]
            if "partialInfo" in props:
                updateKwargs["partialInfo"] = props["partialInfo"]

        submitter.run(props['platform'], props['buildid'], props['appName'],
            props['branch'], props['appVersion'], locale, props['hashType'],
            extVersion, isOSUpdate=isOSUpdate, **updateKwargs)
    elif options.type_ == "release":
        updateKwargs = {}
        if options.schema_version == 2:
            submitter = ReleaseSubmitterV2(options.api_root, auth, options.dummy)
            updateKwargs['completeMarSize'] = props['completeMarSize']
            updateKwargs['completeMarHash'] = props['completeMarHash']
            updateKwargs['completeMarUrl'] = props['completeMarUrl']
        else:
            submitter = ReleaseSubmitterV3(options.api_root, auth, options.dummy)
            updateKwargs["completeInfo"] = [{
                'size': props['completeMarSize'],
                'hash': props['completeMarHash'],
            }]
            if "partialInfo" in props:
                updateKwargs["partialInfo"] = props["partialInfo"]

        submitter.run(props['platform'], props['appName'], props['appVersion'],
            props['version'], props['build_number'], locale,
            props['hashType'], extVersion, props['buildid'],
            **updateKwargs)
    else:
        parser.error("Invalid value for --type")
