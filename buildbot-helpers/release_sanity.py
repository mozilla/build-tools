#!/usr/bin/env python
"""%prog [-d|--dryrun] [-u|--username `username`] [-b|--bypasscheck]
        [-V| --version `version`] [-B --branch `branchname`]
        [-N|--build-number `buildnumber`] master:port

    Wrapper script to sanity-check a release. Default behaviour is to reconfig
    the master, check the branch and revision specific in the release_configs
    exit, check if the milestone and version# in the source repo match the
    expected values in the release_configs
"""
import re, urllib2
from optparse import OptionParser
from util.commands import run_cmd
from util.file import compare
from util.hg import make_hg_url
from release.info import readReleaseConfig
import logging
log = logging.getLogger(__name__)

def compareVersion(fileHandle, versionNumber):
    """Given an open readable file-handle look for the occurrence
       of the version # in the file"""
    log.info("looking for %s in %s" % (versionNumber, fileHandle.geturl()))
    ret = re.search(re.compile(re.escape(versionNumber), re.DOTALL), fileHandle.read())
    if ret:
        log.info("Found a match!")
    return ret

def reconfig():
    """reconfig the master in the cwd"""
    run_cmd(['make', 'reconfig'])

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

def verify_build(branch, revision, hghost, version, milestone):
    """Pull down the version.txt, milestone.txt and js/src/config/milestone.txt
       and make sure it matches the release configs"""
    version_url = make_hg_url(
            hghost,
            branch,
            revision=revision,
            filename='browser/config/version.txt'
            )
    milestone_url = make_hg_url(
            hghost,
            branch,
            revision=revision,
            filename='config/milestone.txt'
            )
    js_milestone_url = make_hg_url(
            hghost,
            branch,
            revision=revision,
            filename='js/src/config/milestone.txt'
            )
    success = True
    try:
        version_file = urllib2.urlopen(version_url)
        if not compareVersion(version_file, version):
            log.error("compare to milestone.txt/version.txt failed. Check again, or -b to bypass")
            success = False
        milestone_file = urllib2.urlopen(milestone_url)
        if not compareVersion(milestone_file, milestone):
            log.error("compare to version.txt failed. Check again, or -b to bypass")
            success = False
        js_milestone_file = urllib2.urlopen(js_milestone_url)
        if not compareVersion(js_milestone_file, milestone):
            log.error("compare to js/src/config/milestone.txt failed. Check again, or -b to bypass")
            success = False
    except urllib2.HTTPError, inst:
        log.error("cannot find %s. Check again, or -b to bypass" % inst.geturl())
        success = False

    return success

def verify_configs(branch, revision, hghost, configs_repo, staging, changesets):
    """Check the release_configs and l10n-changesets against tagged revisions"""
    if staging:
        filename = "staging_release-firefox-%s.py" % branch
        configs_url = make_hg_url(hghost, configs_repo, revision=revision, filename="mozilla/%s" % filename)
    else:
        filename = "release-firefox-%s.py" % branch
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
            staging = False,
            )
    parser.add_option("-s", "--staging", dest="staging", action="store_true",
            help="use staging configs")
    parser.add_option("-b", "--bypass-check", dest="check", action="store_false",
            help="don't bother verifying release repo's on this master")
    parser.add_option("-d", "--dryrun", dest="dryrun", action="store_true",
            help="just do the reconfig/checks, without starting anything")
    parser.add_option("-u", "--username", dest="username",
            help="specify a specific username to attach to the sendchange (cltbld)")
    parser.add_option("-V", "--version", dest="version",
            help="firefox version string for release in format: x.x.x")
    parser.add_option("-N", "--build-number", dest="buildNumber",
            help="buildNumber for this release, uses release_config otherwise")
    parser.add_option("-B", "--branch", dest="branch",
            help="branch name for this release, uses release_config otherwise")

    options, args = parser.parse_args()
    if not options.dryrun and not args:
        parser.error("Need to provide a master to sendchange to, or -d for a dryrun")
    elif not options.branch:
        parser.error("Need to provide a branch to release")

    logging.basicConfig(level=options.loglevel,
            format="%(asctime)s : %(levelname)s : %(message)s")

    if options.staging:
        releaseConfigFile = "staging_release-firefox-%s.py" % options.branch
    else:
        releaseConfigFile = "release-firefox-%s.py" % options.branch
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
                options.branch,
                "%s_BUILD%s" % (releaseConfig['baseTag'], options.buildNumber),
                branchConfig['hghost'],
                GLOBAL_VARS['config_repo_path'],
                options.staging,
                releaseConfig['l10nRevisionFile'],
                ):
            test_success = False
            log.error("Error verifying configs")

        #verify that the relBranch + revision in the release_configs exists in hg
        if not verify_repo(
                releaseConfig['sourceRepoPath'],
                releaseConfig['sourceRepoRevision'],
                branchConfig['hghost']
                ):
            test_success = False
            log.error("Error verifying repos")

        #if this is a respin, verify that the version/milestone files have been bumped
        if options.buildNumber > 1:
            if not verify_build(
                    releaseConfig['sourceRepoPath'],
                    releaseConfig['sourceRepoRevision'],
                    branchConfig['hghost'],
                    releaseConfig['version'],
                    releaseConfig['milestone'],
                    ):
                test_success = False

    if test_success:
        if not options.dryrun:
            reconfig()
            sendchange(
                    releaseConfig['sourceRepoPath'],
                    "%s_RELEASE" % releaseConfig['baseTag'],
                    options.username,
                    args[0],
                    releaseConfigFile,
                    )
        else:
            log.info("Tests Passed! Did not run reconfig/sendchange. Rerun without `-d`")
    else:
        log.fatal("Tests Failed! Not running sendchange!")
