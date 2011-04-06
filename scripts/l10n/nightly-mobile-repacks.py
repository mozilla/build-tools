#!/usr/bin/env python

import logging
import os
from os import path
import sys

sys.path.append(path.join(path.dirname(__file__), "../../lib/python"))

from build.download import downloadNightlyBuild
from build.l10n import repackLocale, l10nRepackPrep, getNightlyLocalesForChunk
import build.misc
from build.paths import getLatestDir
from build.upload import postUploadCmdPrefix
from release.info import readBranchConfig
from util.commands import run_cmd
from util.hg import mercurial, update, make_hg_url

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

HG="hg.mozilla.org"
DEFAULT_BUILDBOT_CONFIGS_REPO=make_hg_url(HG, "build/buildbot-configs")

class RepackError(Exception):
    pass

def createRepacks(sourceRepo, mobileRepo, l10nRepoDir, l10nBaseRepo,
                  mozconfigPath, objdir, makeDirs, locales, ftpProduct,
                  stageServer, stageUsername, stageSshKey, compareLocalesRepo,
                  merge, platform):
    sourceRepoName = path.split(sourceRepo)[-1]
    mobileDirName = "mobile"
    localeSrcDir = path.join(sourceRepoName, objdir, mobileDirName, "locales")
    # Even on Windows we need to use "/" as a separator for this because
    # compare-locales doesn"t work any other way
    l10nIni = "/".join([sourceRepoName, mobileDirName, "locales", "l10n.ini"])

    env = {
        "MOZ_OBJDIR": objdir,
        "UPLOAD_HOST": stageServer,
        "UPLOAD_USER": stageUsername,
        "UPLOAD_SSH_KEY": stageSshKey,
        "UPLOAD_TO_TEMP": "1",
        "EN_US_BINARY_URL": getLatestDir(
            ftpProduct, sourceRepoName, platform, protocol="http",
            server=stageServer
        )
    }
    build.misc.cleanupObjdir(sourceRepoName, objdir, mobileDirName)
    mercurial(sourceRepo, sourceRepoName)
    if mobileRepo:
        mercurial(mobileRepo, path.join(sourceRepoName, mobileDirName))
    l10nRepackPrep(sourceRepoName, objdir, mozconfigPath,
                   l10nRepoDir, makeDirs, localeSrcDir, env)
    buildInfo = downloadNightlyBuild(localeSrcDir, env)
    run_cmd(["hg", "update", "-r", buildInfo["gecko_revision"]],
            cwd=sourceRepoName)
    run_cmd(["hg", "update", "-r", buildInfo["fennec_revision"]],
            cwd=path.join(sourceRepoName, mobileDirName))
    env["POST_UPLOAD_CMD"] = postUploadCmdPrefix(
        to_latest=True,
        branch="%s-%s-l10n" % (sourceRepoName, platform),
        product=ftpProduct
    )

    err = False
    for l in locales:
        try:
            repackLocale(l, l10nRepoDir, l10nBaseRepo, "default",
                         localeSrcDir, l10nIni, compareLocalesRepo, env, merge)
        except Exception, e:
            err = True
            log.error("Error creating locale '%s': %s", l, e)
            pass

    if err:
        raise RepackError("At least one repack failed, see above")

REQUIRED_BRANCH_CONFIG = ("repo_path", "l10n_repo_path",
                          "stage_ssh_key", "stage_server",
                          "stage_username", "compare_locales_repo_path")

def validate(options, args):
    err = False
    if not options.configfile:
        log.info("Must pass --configfile")
        sys.exit(1)
    branchConfigFile = path.join("buildbot-configs", options.configfile)
    branchConfigDir = path.dirname(branchConfigFile)

    if not path.exists(branchConfigFile):
        log.info("%s does not exist!" % branchConfigFile)
        sys.exit(1)

    if not options.branch:
        err = True
        log.error("branch is required")
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
        branchConfig = readBranchConfig(branchConfigDir, branchConfigFile,
                                        path.basename(options.branch),
                                        required=REQUIRED_BRANCH_CONFIG)
    except:
        err = True

    if err:
        sys.exit(1)
    return branchConfig

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser("")

    makeDirs = []

    parser.set_defaults(
        buildbotConfigs=os.environ.get("BUILDBOT_CONFIGS",
                                       DEFAULT_BUILDBOT_CONFIGS_REPO),
        locales=[],
        chunks=None,
        thisChunk=None,
        objdir="obj-l10n"
    )
    parser.add_option("-c", "--configfile", dest="configfile")
    parser.add_option("-B", "--branch", dest="branch")
    parser.add_option("-m", "--mobile-branch", dest="mobileBranch")
    parser.add_option("-b", "--buildbot-configs", dest="buildbotConfigs")
    parser.add_option("-p", "--platform", dest="platform")
    parser.add_option("-o", "--objdir", dest="objdir")
    parser.add_option("-l", "--locale", dest="locales", action="append")
    parser.add_option("--chunks", dest="chunks", type="int")
    parser.add_option("--this-chunk", dest="thisChunk", type="int")

    options, args = parser.parse_args()
    mercurial(options.buildbotConfigs, "buildbot-configs")
    update("buildbot-configs", revision="default")
    branchConfig = validate(options, args)
    platformConfig = branchConfig["mobile_platforms"][options.platform]

    mozconfig = path.join("buildbot-configs", "mozilla2",
                          platformConfig["mozconfig"], "l10n-mozconfig")
    if options.chunks:
        if options.mobileBranch:
            locales = getNightlyLocalesForChunk("",
                options.mobileBranch, options.platform,
                options.chunks, options.thisChunk)
        else:
            locales = getNightlyLocalesForChunk("mobile",
                options.branch, options.platform,
                options.chunks, options.thisChunk)
    else:
        locales = options.locales

    ftpProduct = "mobile"
    l10nRepoDir = path.split(branchConfig["l10n_repo_path"])[-1]
    stageSshKey = path.join("~", ".ssh", branchConfig["stage_ssh_key"])
    try:
        hg = branchConfig["hghost"]
    except:
        hg = HG
    try:
        merge = platformConfig["merge_locales"]
    except:
        merge = True

    mobileRepo = None
    if options.mobileBranch:
        mobileRepo = make_hg_url(hg, options.mobileBranch)
    createRepacks(
        make_hg_url(hg, options.branch),
        mobileRepo, l10nRepoDir,
        make_hg_url(hg, branchConfig["l10n_repo_path"]), mozconfig,
        options.objdir, makeDirs, locales, ftpProduct,
        branchConfig["stage_server"], branchConfig["stage_username"],
        stageSshKey,
        make_hg_url(hg, branchConfig["compare_locales_repo_path"]), merge,
        options.platform)
