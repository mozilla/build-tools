#!/usr/bin/env python
"""%prog [-d|--dryrun] [-u|--username `username`] [-b|--bypasscheck]
        [-V| --version `version`] [-B --branch `branchname`]
        [-N|--build-number `buildnumber`]
        [-c| --release-config `releaseConfigFile`] master:port

    Wrapper script to sanity-check a release. Default behaviour is to reconfig
    the master, check the branch and revision specific in the release_configs
    exit, check if the milestone and version# in the source repo match the
    expected values in the release_configs
"""
import re, urllib2
import os
from optparse import OptionParser
from util.commands import run_cmd
from util.file import compare
from util.hg import make_hg_url
from release.info import readReleaseConfig, getRepoMatchingBranch
import logging
log = logging.getLogger(__name__)

RECONFIG_SCRIPT = os.path.join(os.path.dirname(__file__),
                               "../buildfarm/maintenance/buildbot-wrangler.py")
def findVersion(contents, versionNumber):
    """Given an open readable file-handle look for the occurrence
       of the version # in the file"""
    ret = re.search(re.compile(re.escape(versionNumber), re.DOTALL), contents)
    return ret

def reconfig():
    """reconfig the master in the cwd"""
    run_cmd(['python', RECONFIG_SCRIPT, 'reconfig', os.getcwd()])

def sendchange(branch, revision, username, master, configfile):
    """Send the change to buildbot to kick off the release automation"""
    cmd = [
       'buildbot',
       'sendchange',
       '--username',
       username,
       '--master',
       master,
       '--branch',
       branch,
       '-p',
       'release_config:mozilla/%s' % configfile,
       '-p',
       'script_repo_revision:%s' % revision,
       'release_build'
       ]
    log.info("Executing: %s" % cmd)
    run_cmd(cmd)

def verify_repo(branch, revision, hghost):
    """Poll the hgweb interface for a given branch and revision to
       make sure it exists"""
    repo_url = make_hg_url(hghost, branch, revision=revision)
    log.info("Checking for existence of %s..." % repo_url)
    success = True
    try:
        repo_page = urllib2.urlopen(repo_url)
        log.info("Got: %s !" % repo_page.geturl())
    except urllib2.HTTPError:
        log.error("Repo does not exist with required revision. Check again, or use -b to bypass")
        success = False
    return success

def verify_build(sourceRepo, hghost):
    """ Ensure that the bumpFiles match what the release config wants them to be"""
    success = True
    for filename, versions in sourceRepo['bumpFiles'].iteritems():
        try:
            url = make_hg_url(hghost, sourceRepo['path'],
                              revision=sourceRepo['revision'],
                              filename=filename)
            found_version = urllib2.urlopen(url).read()
            if not findVersion(found_version, versions['version']):
                log.error("%s has incorrect version '%s' (expected '%s')" % \
                  (filename, found_version, versions['version']))
                success = False
        except urllib2.HTTPError, inst:
            log.error("cannot find %s. Check again, or -b to bypass" % inst.geturl())
            success = False

    return success

def verify_configs(revision, hghost, configs_repo, changesets, filename):
    """Check the release_configs and l10n-changesets against tagged revisions"""
    configs_url = make_hg_url(hghost, configs_repo, revision=revision, filename="mozilla/%s" % filename)
    l10n_url = make_hg_url(hghost, configs_repo, revision=revision, filename="mozilla/%s" % changesets)

    success = True
    try:
        official_configs = urllib2.urlopen(configs_url)
        log.info("Comparing tagged revision %s to on-disk %s ..." % (configs_url, filename))
        if not compare(official_configs, filename):
            log.error("local configs do not match tagged revisions in repo")
            success = False
        l10n_changesets = urllib2.urlopen(l10n_url)
        log.info("Comparing tagged revision %s to on-disk %s ..." % (l10n_url, changesets))
        if not compare(l10n_changesets, changesets):
            log.error("local l10n-changesets do not match tagged revisions in repo")
            success = False
    except urllib2.HTTPError:
        log.error("cannot find configs in repo %s" % configs_url)
        log.error("cannot find configs in repo %s" % l10n_url)
        success = False
    return success

def verify_options(cmd_options, config):
    """Check release_configs against command-line opts"""
    success = True
    if cmd_options.version != config['version']:
        log.error("version passed in does not match release_configs")
        success = False
    if int(cmd_options.buildNumber) != int(config['buildNumber']):
        log.error("buildNumber passed in does not match release_configs")
        success = False
    if not getRepoMatchingBranch(cmd_options.branch, config['sourceRepositories']):
        log.error("branch passed in does not exist in release config")
        success = False
    return success

if __name__ == '__main__':
    from localconfig import GLOBAL_VARS
    parser = OptionParser(__doc__)
    parser.set_defaults(
            check = True,
            dryrun = False,
            username = "cltbld",
            loglevel = logging.INFO,
            version = None,
            buildNumber = None,
            branch = None,
            releaseConfig = None,
            )
    parser.add_option("-b", "--bypass-check", dest="check", action="store_false",
            help="don't bother verifying release repo's on this master")
    parser.add_option("-d", "--dryrun", dest="dryrun", action="store_true",
            help="just do the reconfig/checks, without starting anything")
    parser.add_option("-u", "--username", dest="username",
            help="specify a specific username to attach to the sendchange (cltbld)")
    parser.add_option("-V", "--version", dest="version",
            help="firefox version string for release in format: x.x.x")
    parser.add_option("-N", "--build-number", dest="buildNumber", type="int",
            help="buildNumber for this release, uses release_config otherwise")
    parser.add_option("-B", "--branch", dest="branch",
            help="branch name for this release, uses release_config otherwise")
    parser.add_option("-c", "--release-config", dest="releaseConfig",
            help="override the default release-config file")

    options, args = parser.parse_args()
    if not options.dryrun and not args:
        parser.error("Need to provide a master to sendchange to, or -d for a dryrun")
    elif not options.branch:
        parser.error("Need to provide a branch to release")
    elif not options.releaseConfig:
        parser.error("Need to provide a release config file")

    logging.basicConfig(level=options.loglevel,
            format="%(asctime)s : %(levelname)s : %(message)s")

    releaseConfigFile = options.releaseConfig
    releaseConfig = readReleaseConfig(releaseConfigFile)

    if not options.version:
        log.warn("No version specified, using version in release_config, which may be out of date!")
        options.version = releaseConfig['version']
    if not options.buildNumber:
        log.warn("No buildNumber specified, using buildNumber in release_config, which may be out of date!")
        options.buildNumber = releaseConfig['buildNumber']

    test_success = True
    if options.check:
        from config import BRANCHES
        branchConfig = BRANCHES[options.branch]
        #Match command line options to defaults in release_configs
        if not verify_options(options, releaseConfig):
            test_success = False
            log.error("Error verifying command-line options, attempting checking repo")

        #verify that the release_configs on-disk match the tagged revisions in hg
        if not verify_configs(
                "%s_BUILD%s" % (releaseConfig['baseTag'], options.buildNumber),
                branchConfig['hghost'],
                GLOBAL_VARS['config_repo_path'],
                releaseConfig['l10nRevisionFile'],
                releaseConfigFile,
                ):
            test_success = False
            log.error("Error verifying configs")

        #verify that the relBranch + revision in the release_configs exists in hg
        for sr in releaseConfig['sourceRepositories'].values():
            sourceRepoPath = sr.get('clonePath', sr['path'])
            if not verify_repo(sourceRepoPath, sr['revision'],
                               branchConfig['hghost']):
                test_success = False
                log.error("Error verifying repos")

        #if this is a respin, verify that the version/milestone files have been bumped
        if options.buildNumber > 1:
            for sr in releaseConfig['sourceRepositories'].values():
                if not verify_build(sr, branchConfig['hghost']):
                    test_success = False

    if test_success:
        if not options.dryrun:
            reconfig()
            sourceRepoPath = getRepoMatchingBranch(options.branch, releaseConfig['sourceRepositories'])['path']
            sendchange(
                    sourceRepoPath,
                    "%s_RELEASE" % releaseConfig['baseTag'],
                    options.username,
                    args[0],
                    releaseConfigFile,
                    )
        else:
            log.info("Tests Passed! Did not run reconfig/sendchange. Rerun without `-d`")
    else:
        log.fatal("Tests Failed! Not running sendchange!")
