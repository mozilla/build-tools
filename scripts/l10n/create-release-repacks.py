#!/usr/bin/env python

import logging
import os
from os import path
import sys

sys.path.append(path.join(path.dirname(__file__), "../../lib/python"))

from build.l10n import repackLocale, l10nRepackPrep
import build.misc
from build.upload import postUploadCmdPrefix
from release.download import downloadReleaseBuilds
from release.info import readReleaseConfig, readBranchConfig
from release.l10n import getReleaseLocalesForChunk
from util.hg import mercurial, update, make_hg_url

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

HG="hg.mozilla.org"
DEFAULT_BUILDBOT_CONFIGS_REPO=make_hg_url(HG, "build/buildbot-configs")

class RepackError(Exception):
    pass

def createRepacks(sourceRepo, revision, l10nRepoDir, l10nBaseRepo,
                  mozconfigPath, objdir, makeDirs, appName, locales, product,
                  version, buildNumber, stageServer, stageUsername, stageSshKey,
                  compareLocalesRepo, merge, platform, brand):
    sourceRepoName = path.split(sourceRepo)[-1]
    localeSrcDir = path.join(sourceRepoName, objdir, appName, "locales")
    # Even on Windows we need to use "/" as a separator for this because
    # compare-locales doesn"t work any other way
    l10nIni = "/".join([sourceRepoName, appName, "locales", "l10n.ini"])

    env = {
        "MOZ_OBJDIR": objdir,
        "MOZ_MAKE_COMPLETE_MAR": "1",
        "MOZ_PKG_VERSION": version,
        "UPLOAD_HOST": stageServer,
        "UPLOAD_USER": stageUsername,
        "UPLOAD_SSH_KEY": stageSshKey,
        "UPLOAD_TO_TEMP": "1",
        "MOZ_PKG_PRETTYNAMES": "1",
        "POST_UPLOAD_CMD": postUploadCmdPrefix(
            to_candidates=True,
            product=product,
            version=version,
            buildNumber=buildNumber
        )
    }
    build.misc.cleanupObjdir(sourceRepoName, objdir, appName)
    mercurial(sourceRepo, sourceRepoName)
    update(sourceRepoName, revision=revision)
    l10nRepackPrep(sourceRepoName, objdir, mozconfigPath, l10nRepoDir, makeDirs,
                   localeSrcDir, env)
    input_env = downloadReleaseBuilds(stageServer, product, brand, version,
                                      buildNumber, platform)
    env.update(input_env)

    err = False
    for l in locales:
        try:
            repackLocale(l, l10nRepoDir, l10nBaseRepo, revision,
                         localeSrcDir, l10nIni, compareLocalesRepo, env, merge)
        except Exception, e:
            err = True
            log.error("Error creating locale '%s': %s", l, e)
            pass

    if err:
        raise RepackError("At least one repack failed, see above")

REQUIRED_BRANCH_CONFIG = ("stage_server", "stage_username", "stage_ssh_key",
                          "compare_locales_repo_path", "hghost")
REQUIRED_RELEASE_CONFIG = ("sourceRepositories", "l10nRepoPath", "appName",
                           "productName", "version", "buildNumber")

def validate(options, args):
    err = False
    if not options.configfile:
        log.info("Must pass --configfile")
        sys.exit(1)
    releaseConfigFile = path.join("buildbot-configs", options.releaseConfig)
    branchConfigFile = path.join("buildbot-configs", options.configfile)
    branchConfigDir = path.dirname(branchConfigFile)

    if not path.exists(branchConfigFile):
        log.info("%s does not exist!" % branchConfigFile)
        sys.exit(1)

    if options.chunks or options.thisChunk:
        assert options.chunks and options.thisChunk, \
          "chunks and this-chunk are required when one is passed"
        assert not options.locales, \
          "locale option cannot be used when chunking"
    else:
        if len(options.locales) < 1:
            err = True
            log.error("Need at least one locale to repack")

    try:
        releaseConfig = readReleaseConfig(releaseConfigFile,
                                          required=REQUIRED_RELEASE_CONFIG)
        sourceRepoName = releaseConfig['sourceRepositories'][options.source_repo_key]['name']
        branchConfig = readBranchConfig(branchConfigDir, branchConfigFile,
                                        sourceRepoName,
                                        required=REQUIRED_BRANCH_CONFIG)
    except:
        err = True

    if err:
        sys.exit(1)
    return branchConfig, releaseConfig

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser("")

    makeDirs = ["config", "nsprpub", path.join("modules", "libmar")]

    parser.set_defaults(
        buildbotConfigs=os.environ.get("BUILDBOT_CONFIGS",
                                       DEFAULT_BUILDBOT_CONFIGS_REPO),
        locales=[],
        chunks=None,
        thisChunk=None,
        objdir="obj-l10n",
        source_repo_key="mozilla"
    )
    parser.add_option("-c", "--configfile", dest="configfile")
    parser.add_option("-r", "--release-config", dest="releaseConfig")
    parser.add_option("-b", "--buildbot-configs", dest="buildbotConfigs")
    parser.add_option("-t", "--release-tag", dest="releaseTag")
    parser.add_option("-p", "--platform", dest="platform")
    parser.add_option("-o", "--objdir", dest="objdir")
    parser.add_option("-l", "--locale", dest="locales", action="append")
    parser.add_option("--source-repo-key", dest="source_repo_key")
    parser.add_option("--chunks", dest="chunks", type="int")
    parser.add_option("--this-chunk", dest="thisChunk", type="int")

    options, args = parser.parse_args()
    mercurial(options.buildbotConfigs, "buildbot-configs")
    update("buildbot-configs", revision=options.releaseTag)
    sys.path.append(os.getcwd())
    branchConfig, releaseConfig = validate(options, args)
    sourceRepoInfo = releaseConfig["sourceRepositories"][options.source_repo_key]

    try:
        brandName = releaseConfig["brandName"]
    except KeyError:
        brandName =  releaseConfig["productName"].title()
    mozconfig = path.join("buildbot-configs", "mozilla2", options.platform,
                          sourceRepoInfo['name'], "release", "l10n-mozconfig")
    if options.chunks:
        locales = getReleaseLocalesForChunk(
            releaseConfig["productName"], releaseConfig["appName"],
            releaseConfig["version"], int(releaseConfig["buildNumber"]),
            sourceRepoInfo["path"], options.platform,
            options.chunks, options.thisChunk)
    else:
        locales = options.locales

    try:
        l10nRepoDir = path.split(releaseConfig["l10nRepoClonePath"])[-1]
    except KeyError:
        l10nRepoDir = path.split(releaseConfig["l10nRepoPath"])[-1]

    stageSshKey = path.join("~", ".ssh", branchConfig["stage_ssh_key"])

    createRepacks(
        make_hg_url(branchConfig["hghost"], sourceRepoInfo["path"]),
        options.releaseTag, l10nRepoDir,
        make_hg_url(branchConfig["hghost"], releaseConfig["l10nRepoPath"]),
        mozconfig, options.objdir, makeDirs,
        releaseConfig["appName"], locales, releaseConfig["productName"],
        releaseConfig["version"], int(releaseConfig["buildNumber"]),
        branchConfig["stage_server"], branchConfig["stage_username"],
        stageSshKey,
        make_hg_url(branchConfig["hghost"],
                    branchConfig["compare_locales_repo_path"]),
        releaseConfig["mergeLocales"], options.platform, brandName)
