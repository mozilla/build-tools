#!/usr/bin/env python

import os
from os import path
import sys
import logging

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

sys.path.append(path.join(path.dirname(__file__), "../../lib/python"))
from release.info import readReleaseConfig, readBranchConfig
from release.paths import makeCandidatesDir, makeReleasesDir
from util.hg import update, make_hg_url, mercurial
from util.commands import run_remote_cmd


DEFAULT_BUILDBOT_CONFIGS_REPO = make_hg_url('hg.mozilla.org',
                                            'build/buildbot-configs')

REQUIRED_BRANCH_CONFIG = ("stage_server", "stage_username", "stage_ssh_key")
REQUIRED_RELEASE_CONFIG = ("productName", "version", "buildNumber",
                           "oldVersion", "oldBuildNumber")

def validate(options, args):
    if not options.configfile:
        log.info("Must pass --configfile")
        sys.exit(1)
    releaseConfigFile = path.join("buildbot-configs", options.releaseConfig)
    branchConfigFile = path.join("buildbot-configs", options.configfile)
    branchConfigDir = path.dirname(branchConfigFile)

    if not path.exists(branchConfigFile):
        log.info("%s does not exist!" % branchConfigFile)
        sys.exit(1)

    releaseConfig = readReleaseConfig(releaseConfigFile,
                                      required=REQUIRED_RELEASE_CONFIG)
    sourceRepoName = releaseConfig['sourceRepositories'][options.sourceRepoKey]['name']
    branchConfig = readBranchConfig(branchConfigDir, branchConfigFile,
                                    sourceRepoName,
                                    required=REQUIRED_BRANCH_CONFIG)
    return branchConfig, releaseConfig

def downloadRelease(productName, version, buildNumber, stageServer,
                    stageUsername=None, stageSshKey=None,
                    stageUrlPrefix='http://stage.mozilla.org'):

    candidatesDir = makeCandidatesDir(productName, version,
                                      buildNumber).rstrip('/')
    releasesDir = makeReleasesDir(productName, version).rstrip('/')
    commands = [
        'rm -rf %s' % candidatesDir,
        'rm -rf %s' % releasesDir,
        'mkdir -p %s' % candidatesDir,
        'cd %(candidatesDir)s && \
          wget -nv -r -np -nH --cut-dirs=6 -R index.html* \
          -X %(candidatesDir)s/unsigned \
          -X %(candidatesDir)s/contrib* \
          -X %(candidatesDir)s/partner-repacks \
          -X %(candidatesDir)s/win32-EUballot \
          %(stageUrlPrefix)s%(candidatesDir)s/' % \
          (dict(candidatesDir=candidatesDir, stageUrlPrefix=stageUrlPrefix)),
        'ln -s %s %s' % (candidatesDir, releasesDir),
    ]

    for command in commands:
        run_remote_cmd(command, server=stageServer, username=stageUsername,
                       sshKey=stageSshKey)

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(__doc__)

    parser.set_defaults(
        buildbotConfigs=os.environ.get("BUILDBOT_CONFIGS",
                                       DEFAULT_BUILDBOT_CONFIGS_REPO),
        sourceRepoKey="mozilla"
    )
    parser.add_option("-c", "--configfile", dest="configfile")
    parser.add_option("-r", "--release-config", dest="releaseConfig")
    parser.add_option("-b", "--buildbot-configs", dest="buildbotConfigs")
    parser.add_option("-t", "--release-tag", dest="releaseTag")
    parser.add_option("--source-repo-key", dest="sourceRepoKey")
    parser.add_option("--download-current-release", dest="useCurrentRelease",
                      action="store_true", default=False)

    options, args = parser.parse_args()
    mercurial(options.buildbotConfigs, "buildbot-configs")
    update("buildbot-configs", revision=options.releaseTag)

    branchConfig, releaseConfig = validate(options, args)

    productName = releaseConfig['productName']
    version = releaseConfig['oldVersion']
    buildNumber = releaseConfig['oldBuildNumber']
    if options.useCurrentRelease:
        version = releaseConfig['version']
        buildNumber = releaseConfig['buildNumber']
    stageServer = branchConfig['stage_server']
    stageUsername = branchConfig['stage_username']
    stageSshKey = path.join(os.path.expanduser("~"), ".ssh",
                            branchConfig["stage_ssh_key"])

    downloadRelease(stageServer=stageServer,
                    stageUsername=stageUsername,
                    stageSshKey=stageSshKey,
                    productName=productName,
                    version=version,
                    buildNumber=buildNumber)
