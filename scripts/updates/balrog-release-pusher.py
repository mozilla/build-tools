#!/usr/bin/env python
try:
    import simplejson as json
except ImportError:
    import json

import os
from os import path
import site
import logging
import sys

site.addsitedir(path.join(path.dirname(__file__), "../../lib/python"))

from balrog.submitter.cli import ReleaseCreator, ReleasePusher
from release.info import readReleaseConfig
from util.retry import retry
from util.hg import mercurial, make_hg_url

HG = "hg.mozilla.org"
DEFAULT_BUILDBOT_CONFIGS_REPO = make_hg_url(HG, 'build/buildbot-configs')
REQUIRED_CONFIG = ('appVersion', 'productName', 'version', 'enUSPlatforms',
    'testChannels', 'releaseChannel', 'baseTag', 'buildNumber',
    'partialUpdates', 'stagingServer', 'bouncerServer', 'testChannelRuleIds')

def validate(options):
    err = False
    config = {}

    if not path.exists(path.join('buildbot-configs', options.release_config)):
        print "%s does not exist!" % options.release_config
        sys.exit(1)

    config = readReleaseConfig(path.join('buildbot-configs',
                                         options.release_config))
    for key in REQUIRED_CONFIG:
        if key not in config:
            err = True
            print "Required item missing in config: %s" % key

    if err:
        sys.exit(1)
    return config

if __name__ == '__main__':

    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-p", "--build-properties", dest="build_properties")
    parser.add_option("-b", "--buildbot-configs", dest="buildbot_configs",
                      help="The place to clone buildbot-configs from",
                      default=os.environ.get('BUILDBOT_CONFIGS_REPO',
                                             DEFAULT_BUILDBOT_CONFIGS_REPO))
    parser.add_option("-r", "--release-config", dest="release_config")
    parser.add_option("-a", "--api-root", dest="api_root")
    parser.add_option("-c", "--credentials-file", dest="credentials_file")
    parser.add_option("-u", "--username", dest="username")
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true")
    options, args = parser.parse_args()

    logging_level = logging.INFO
    if options.verbose:
        logging_level = logging.DEBUG
    logging.basicConfig(stream=sys.stdout, level=logging_level,
                        format="%(message)s")

    for opt in ('build_properties', 'release_config', 'api_root', 'credentials_file', 'buildbot_configs', 'username'):
        if not getattr(options, opt):
            print >>sys.stderr, "Required option %s not present" % opt
            sys.exit(1)

    properties = json.load(open(options.build_properties))['properties']
    releaseTag = properties['script_repo_revision']
    hashType = properties['hashType']
    retry(mercurial, args=(options.buildbot_configs, 'buildbot-configs'), kwargs=dict(revision=releaseTag))
    release_config = validate(options)

    credentials = {}
    execfile(options.credentials_file, credentials)
    auth = (options.username, credentials['balrog_credentials'][options.username])
    updateChannels = release_config['testChannels'] + [release_config['releaseChannel']]

    creator = ReleaseCreator(options.api_root, auth)
    creator.run(release_config['appVersion'], release_config['productName'],
                release_config['version'], release_config['buildNumber'],
                release_config['partialUpdates'], updateChannels,
                release_config['stagingServer'], release_config['bouncerServer'],
                release_config['enUSPlatforms'], hashType)

    pusher = ReleasePusher(options.api_root, auth)
    pusher.run(release_config['productName'], release_config['version'],
               release_config['buildNumber'], release_config['testChannelRuleIds'])
