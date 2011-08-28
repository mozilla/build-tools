#!/usr/bin/env python

import os
from os import path
import sys
import logging
from subprocess import CalledProcessError
try:
    import json
except ImportError:
    import simplejson as json

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
REQUIRED_RELEASE_CONFIG = ("productName", "version", "buildNumber")

DEFAULT_RSYNC_EXCLUDES = ['--exclude=*tests*',
                          '--exclude=*crashreporter*',
                          '--exclude=*.log',
                          '--exclude=*.txt',
                          '--exclude=*unsigned*',
                          '--exclude=*update-backup*',
                          '--exclude=*partner-repacks*',
                          '--exclude=*.checksums',
                          '--exclude=logs',
                          '--exclude=jsshell*',
                          ]

VIRUS_SCAN_CMD = ['extract_and_run_command.py', '-j4', 'clamdscan', '-m',
                  '--no-summary', '--']

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


def checkStagePermissions(productName, version, buildNumber, stageServer,
                          stageUsername=None, stageSshKey=None):
    # The following commands should return 0 lines output and exit code 0
    tests = ["find %s ! -user ffxbld ! -path '*/contrib*'",
              "find %s ! -group firefox ! -path '*/contrib*'",
              "find %s -type f ! -perm 644",
              "find %s -mindepth 1 -type d ! -perm 755 ! -path '*/contrib*' ! -path '*/partner-repacks*'",
              "find %s -maxdepth 1 -type d ! -perm 2775 -path '*/contrib*'",
            ]
    candidates_dir = makeCandidatesDir(productName, version, buildNumber)

    errors = False
    for test_template in tests:
        test = test_template % candidates_dir
        cmd = 'test "0" = "$(%s | wc -l)"' % test
        try:
            run_remote_cmd(cmd, server=stageServer,
                           username=stageUsername, sshKey=stageSshKey)
        except CalledProcessError:
            errors = True
            print 'Error while running: %s' % test

    if errors:
        raise

def runAntivirusCheck(productName, version, buildNumber, stageServer,
                      stageUsername=None, stageSshKey=None):
    candidates_dir = makeCandidatesDir(productName, version, buildNumber)
    cmd = VIRUS_SCAN_CMD + [candidates_dir]
    run_remote_cmd(cmd, server=stageServer, username=stageUsername,
                   sshKey=stageSshKey)


def pushToMirrors(productName, version, buildNumber, stageServer,
                  stageUsername=None, stageSshKey=None, excludes=None,
                  extra_excludes=None, dryRun=False):
    """ excludes overrides DEFAULT_RSYNC_EXCLUDES, extra_exludes will be
    appended to DEFAULT_RSYNC_EXCLUDES. """

    source_dir = makeCandidatesDir(productName, version, buildNumber)
    target_dir = makeReleasesDir(productName, version)

    if not excludes:
        excludes = DEFAULT_RSYNC_EXCLUDES
    if extra_excludes:
        excludes += extra_excludes

    # fail if target directory exists
    run_remote_cmd(['test', '!', '-d', target_dir], server=stageServer,
                   username=stageUsername, sshKey=stageSshKey)
    if not dryRun:
        run_remote_cmd(['mkdir', '-p', target_dir], server=stageServer,
                       username=stageUsername, sshKey=stageSshKey)
        run_remote_cmd(['chmod', 'u=rwx,g=rxs,o=rx', target_dir], server=stageServer,
                       username=stageUsername, sshKey=stageSshKey)
    rsync_cmd = ['rsync', '-av' ]
    if dryRun:
        rsync_cmd.append('-n')
    run_remote_cmd(rsync_cmd + excludes + [source_dir, target_dir],
                   server=stageServer, username=stageUsername,
                   sshKey=stageSshKey)

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser("")

    parser.set_defaults(
        buildbotConfigs=os.environ.get("BUILDBOT_CONFIGS",
                                       DEFAULT_BUILDBOT_CONFIGS_REPO),
        sourceRepoKey="mozilla",
    )
    parser.add_option("-c", "--configfile", dest="configfile")
    parser.add_option("-r", "--release-config", dest="releaseConfig")
    parser.add_option("-b", "--buildbot-configs", dest="buildbotConfigs")
    parser.add_option("-t", "--release-tag", dest="releaseTag")
    parser.add_option("--source-repo-key", dest="sourceRepoKey")

    options, args = parser.parse_args()
    mercurial(options.buildbotConfigs, "buildbot-configs")
    update("buildbot-configs", revision=options.releaseTag)

    branchConfig, releaseConfig = validate(options, args)

    productName = releaseConfig['productName']
    version = releaseConfig['version']
    buildNumber = releaseConfig['buildNumber']
    stageServer = branchConfig['stage_server']
    stageUsername = branchConfig['stage_username']
    stageSshKey = path.join(os.path.expanduser("~"), ".ssh",
                            branchConfig["stage_ssh_key"])

    if 'permissions' in args:
        checkStagePermissions(stageServer=stageServer,
                              stageUsername=stageUsername,
                              stageSshKey=stageSshKey,
                              productName=productName,
                              version=version,
                              buildNumber=buildNumber)

    if 'antivirus' in args:
        runAntivirusCheck(stageServer=stageServer,
                          stageUsername=stageUsername,
                          stageSshKey=stageSshKey,
                          productName=productName,
                          version=version,
                          buildNumber=buildNumber)

    if 'permissions' in args or 'antivirus' in args:
        pushToMirrors(stageServer=stageServer,
                      stageUsername=stageUsername,
                      stageSshKey=stageSshKey,
                      productName=productName,
                      version=version,
                      buildNumber=buildNumber,
                      dryRun=True)

    if 'push' in args:
        pushToMirrors(stageServer=stageServer,
                      stageUsername=stageUsername,
                      stageSshKey=stageSshKey,
                      productName=productName,
                      version=version,
                      buildNumber=buildNumber)
