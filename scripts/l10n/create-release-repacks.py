#!/usr/bin/env python

import logging
import os
from os import path
from traceback import format_exc
import sys

sys.path.append(path.join(path.dirname(__file__), "../../lib/python"))

from build.l10n import repackLocale, l10nRepackPrep
import build.misc
from build.upload import postUploadCmdPrefix
from release.download import downloadReleaseBuilds, downloadUpdateIgnore404
from release.info import readReleaseConfig
from release.l10n import getReleaseLocalesForChunk
from util.hg import mercurial, update, make_hg_url
from util.retry import retry

logging.basicConfig(
    stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

HG = "hg.mozilla.org"
DEFAULT_BUILDBOT_CONFIGS_REPO = make_hg_url(HG, "build/buildbot-configs")


class RepackError(Exception):
    pass


def createRepacks(sourceRepo, revision, l10nRepoDir, l10nBaseRepo,
                  mozconfigPath, srcMozconfigPath, objdir, makeDirs, appName,
                  locales, product, version, buildNumber,
                  stageServer, stageUsername, stageSshKey,
                  compareLocalesRepo, merge, platform, brand,
                  generatePartials=False, partialUpdates=None,
                  appVersion=None, usePymake=False, tooltoolManifest=None,
                  tooltool_script=None, tooltool_urls=None):
    sourceRepoName = path.split(sourceRepo)[-1]
    localeSrcDir = path.join(sourceRepoName, objdir, appName, "locales")
    # Even on Windows we need to use "/" as a separator for this because
    # compare-locales doesn"t work any other way
    l10nIni = "/".join([sourceRepoName, appName, "locales", "l10n.ini"])

    env = {
        "MOZ_OBJDIR": objdir,
        #FIXME: "MOZ_MAKE_COMPLETE_MAR": "1",
        "UPLOAD_HOST": stageServer,
        "UPLOAD_USER": stageUsername,
        "UPLOAD_SSH_KEY": stageSshKey,
        "UPLOAD_TO_TEMP": "1",
        "MOZ_PKG_PRETTYNAMES": "1",
        "MOZILLA_REV": os.getenv('MOZILLA_REV', ''),
        "COMM_REV": os.getenv('COMM_REV', ''),
        "LD_LIBRARY_PATH": os.getenv("LD_LIBRARY_PATH", "")
    }
    if appVersion is None or version != appVersion:
        env["MOZ_PKG_VERSION"] = version
    signed = False
    if os.environ.get('MOZ_SIGN_CMD'):
        env['MOZ_SIGN_CMD'] = os.environ['MOZ_SIGN_CMD']
        signed = True
    env['POST_UPLOAD_CMD'] = postUploadCmdPrefix(
        to_candidates=True,
        product=product,
        version=version,
        buildNumber=buildNumber,
        signed=signed,
    )
    if usePymake:
        env['USE_PYMAKE'] = "1"
        # HACK!! We need to get rid of this script, ideally by 25.0b1
        env["INCLUDE"] = "d:\\msvs10\\vc\\include;d:\\msvs10\\vc\\atlmfc\\include;d:\\sdks\\v7.0\\include;d:\\sdks\\v7.0\\include\\atl;d:\\msvs8\\VC\\PlatformSDK\\include;d:\\sdks\\dx10\\include"
        env["LIBPATH"] = "d:\\msvs10\\vc\\lib;d:\\msvs10\\vc\\atlmfc\\lib;\\c\\WINDOWS\\Microsoft.NET\\Framework\\v2.0.50727"
        env["LIB"] = "d:\\msvs10\\vc\\lib;d:\\msvs10\\vc\\atlmfc\\lib;d:\\sdks\\v7.0\\lib;d:\\msvs8\\VC\\PlatformSDK\\lib;d:\\msvs8\\SDK\\v2.0\\lib;d:\\mozilla-build\\atlthunk_compat;d:\\sdks\\dx10\\lib\\x86"
        env["PATH"] = "d:\\msvs10\\VSTSDB\\Deploy;d:\\msvs10\\Common7\\IDE\\;d:\\msvs10\\VC\\BIN;d:\\msvs10\\Common7\\Tools;d:\\msvs10\\VC\\VCPackages;%s" % os.environ["PATH"]
        env["WIN32_REDIST_DIR"] = "d:\\msvs10\\VC\\redist\\x86\\Microsoft.VC100.CRT"
    build.misc.cleanupObjdir(sourceRepoName, objdir, appName)
    retry(mercurial, args=(sourceRepo, sourceRepoName))
    update(sourceRepoName, revision=revision)
    l10nRepackPrep(
        sourceRepoName, objdir, mozconfigPath, srcMozconfigPath, l10nRepoDir,
        makeDirs, localeSrcDir, env, tooltoolManifest, tooltool_script, tooltool_urls)
    input_env = retry(downloadReleaseBuilds,
                      args=(stageServer, product, brand, version, buildNumber,
                            platform),
                      kwargs={'signed': signed})
    env.update(input_env)

    failed = []
    for l in locales:
        try:
            if generatePartials:
                for oldVersion in partialUpdates:
                    oldBuildNumber = partialUpdates[oldVersion]['buildNumber']
                    partialUpdates[oldVersion]['mar'] = retry(
                        downloadUpdateIgnore404,
                        args=(stageServer, product, oldVersion, oldBuildNumber,
                              platform, l)
                    )
            repackLocale(locale=l, l10nRepoDir=l10nRepoDir,
                         l10nBaseRepo=l10nBaseRepo, revision=revision,
                         localeSrcDir=localeSrcDir, l10nIni=l10nIni,
                         compareLocalesRepo=compareLocalesRepo, env=env,
                         merge=merge,
                         productName=product, platform=platform,
                         version=version, partialUpdates=partialUpdates,
                         buildNumber=buildNumber, stageServer=stageServer)
        except Exception, e:
            failed.append((l, format_exc()))

    if len(failed) > 0:
        log.error("The following tracebacks were detected during repacks:")
        for l, e in failed:
            log.error("%s:" % l)
            log.error("%s\n" % e)
        raise Exception(
            "Failed locales: %s" % " ".join([x for x, _ in failed]))

REQUIRED_BRANCH_CONFIG = ("stage_server", "stage_username", "stage_ssh_key",
                          "compare_locales_repo_path", "hghost")
REQUIRED_RELEASE_CONFIG = ("sourceRepositories", "l10nRepoPath", "appName",
                           "productName", "version", "buildNumber")


def validate(options, args):
    if not options.configfile:
        log.info("Must pass --configfile")
        sys.exit(1)
    releaseConfigFile = "/".join(["buildbot-configs", options.releaseConfig])

    if options.chunks or options.thisChunk:
        assert options.chunks and options.thisChunk, \
            "chunks and this-chunk are required when one is passed"
        assert not options.locales, \
            "locale option cannot be used when chunking"
    else:
        if len(options.locales) < 1:
            raise Exception('Need at least one locale to repack')

    releaseConfig = readReleaseConfig(releaseConfigFile,
                                      required=REQUIRED_RELEASE_CONFIG)
    branchConfig = {
        'stage_ssh_key': options.stage_ssh_key,
        'hghost': options.hghost,
        'stage_server': options.stage_server,
        'stage_username': options.stage_username,
        'compare_locales_repo_path': options.compare_locales_repo_path,
    }
    return branchConfig, releaseConfig

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser("")

    makeDirs = ["config"]

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
    parser.add_option("--generate-partials", dest="generatePartials",
                      action='store_true', default=False)
    parser.add_option("--stage-ssh-key", dest="stage_ssh_key")
    parser.add_option("--hghost", dest="hghost")
    parser.add_option("--stage-server", dest="stage_server")
    parser.add_option("--stage-username", dest="stage_username")
    parser.add_option(
        "--compare-locales-repo-path", dest="compare_locales_repo_path")
    parser.add_option("--properties-dir", dest="properties_dir")
    parser.add_option("--tooltool-manifest", dest="tooltool_manifest")
    parser.add_option("--tooltool-script", dest="tooltool_script",
                      default="/tools/tooltool.py")
    parser.add_option("--tooltool-url", dest="tooltool_urls", action="append")
    parser.add_option("--use-pymake", dest="use_pymake",
                      action="store_true", default=False)

    options, args = parser.parse_args()
    retry(mercurial, args=(options.buildbotConfigs, "buildbot-configs"))
    update("buildbot-configs", revision=options.releaseTag)
    sys.path.append(os.getcwd())
    branchConfig, releaseConfig = validate(options, args)
    sourceRepoInfo = releaseConfig["sourceRepositories"][
        options.source_repo_key]

    try:
        brandName = releaseConfig["brandName"]
    except KeyError:
        brandName = releaseConfig["productName"].title()
    platform = options.platform
    if platform == "linux":
        platform = "linux32"
    mozconfig = path.join(sourceRepoInfo['name'], releaseConfig["appName"],
                          "config", "mozconfigs", platform,
                          "l10n-mozconfig")

    if options.chunks:
        locales = retry(getReleaseLocalesForChunk,
                        args=(
                        releaseConfig[
                        "productName"], releaseConfig["appName"],
                        releaseConfig[
                        "version"], int(releaseConfig["buildNumber"]),
                        sourceRepoInfo["path"], options.platform,
                        options.chunks, options.thisChunk)
                        )
    else:
        locales = options.locales

    if options.properties_dir:
        # Output a list of the locales into the properties directory. This will
        # allow consumers of the Buildbot JSON to know which locales were built
        # in a particular repack chunk.
        localeProps = path.normpath(path.join(options.properties_dir, 'locales'))
        f = open(localeProps, 'w+')
        f.write('locales:%s' % ','.join(locales))
        f.close()

    try:
        l10nRepoDir = path.split(releaseConfig["l10nRepoClonePath"])[-1]
    except KeyError:
        l10nRepoDir = path.split(releaseConfig["l10nRepoPath"])[-1]

    stageSshKey = path.join("~", ".ssh", branchConfig["stage_ssh_key"])

    # If mozilla_dir is defined, extend the paths in makeDirs with the prefix
    # of the mozilla_dir
    if 'mozilla_dir' in releaseConfig:
        for i in range(0, len(makeDirs)):
            makeDirs[i] = path.join(releaseConfig['mozilla_dir'], makeDirs[i])

    createRepacks(
        sourceRepo=make_hg_url(branchConfig["hghost"], sourceRepoInfo["path"]),
        revision=options.releaseTag,
        l10nRepoDir='l10n',
        l10nBaseRepo=make_hg_url(branchConfig["hghost"],
                                 releaseConfig["l10nRepoPath"]),
        mozconfigPath=mozconfig,
        srcMozconfigPath=releaseConfig.get('l10n_mozconfigs', {}).get(options.platform),
        objdir=options.objdir,
        makeDirs=makeDirs,
        appName=releaseConfig["appName"],
        locales=locales,
        product=releaseConfig["productName"],
        version=releaseConfig["version"],
        appVersion=releaseConfig["appVersion"],
        buildNumber=int(releaseConfig["buildNumber"]),
        stageServer=branchConfig["stage_server"],
        stageUsername=branchConfig["stage_username"],
        stageSshKey=stageSshKey,
        compareLocalesRepo=make_hg_url(branchConfig["hghost"],
                                       branchConfig[
                                           "compare_locales_repo_path"]),
        merge=releaseConfig["mergeLocales"],
        platform=options.platform,
        brand=brandName,
        generatePartials=options.generatePartials,
        partialUpdates=releaseConfig["partialUpdates"],
        usePymake=options.use_pymake,
        tooltoolManifest=options.tooltool_manifest,
        tooltool_script=options.tooltool_script,
        tooltool_urls=options.tooltool_urls,
    )
