#!/usr/bin/env python
"""%prog [-d|--dryrun] [-u|--username `username`] [-b|--bypass-check]
        [-V| --version `version`] [-B --branch `branchname`]
        [-N|--build-number `buildnumber`]
        [-c| --release-config `releaseConfigFile`]
        [-w| --whitelist `mozconfig_whitelist`]
        -p|--products firefox,fennec master:port

    Wrapper script to sanity-check a release. Default behaviour is to check 
    the branch and revision specific in the release_configs, check if the 
    milestone and version# in the source repo match the
    expected values in the release_configs, check the l10n repos & dashboard,
    compare the nightly and release mozconfigs for a release branch against
    a whitelist of known differences between the two. If all tests pass then 
    the master is reconfiged and then a senchange is generated to kick off
    the release automation.
"""
import re, urllib2
import os, difflib
try:
    import simplejson as json
except ImportError:
    import json
from optparse import OptionParser
from util.commands import run_cmd
from util.file import compare
from util.hg import make_hg_url
from release.info import readReleaseConfig, getRepoMatchingBranch, readConfig
from release.versions import getL10nDashboardVersion
from release.l10n import getShippedLocales
from release.platforms import getLocaleListFromShippedLocales
import logging
from subprocess import CalledProcessError
log = logging.getLogger(__name__)

RECONFIG_SCRIPT = os.path.join(os.path.dirname(__file__),
                               "../buildfarm/maintenance/buildbot-wrangler.py")
error_tally = set()

def findVersion(contents, versionNumber):
    """Given an open readable file-handle look for the occurrence
       of the version # in the file"""
    ret = re.search(re.compile(re.escape(versionNumber), re.DOTALL), contents)
    return ret

def reconfig():
    """reconfig the master in the cwd"""
    run_cmd(['python', RECONFIG_SCRIPT, 'reconfig', os.getcwd()])

def check_buildbot():
    """check if buildbot command works"""
    try:
        run_cmd(['buildbot', '--version'])
    except CalledProcessError:
        print "FAIL: buildbot command doesn't work"
        raise

def locale_diff(locales1,locales2):
    """ accepts two lists and diffs them both ways, returns any differences found """
    diff_list = [locale for locale in locales1 if not locale in locales2]
    diff_list.extend(locale for locale in locales2 if not locale in locales1)
    return diff_list

def sendchange(branch, revision, username, master, products):
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
       'products:%s' % products,
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
        error_tally.add('verify_repo')
    return success

def verify_mozconfigs(branch, revision, hghost, product, mozconfigs, appName, whitelist=None):
    """Compare nightly mozconfigs for branch to release mozconfigs and compare to whitelist of known differences"""
    if whitelist:
        mozconfigWhitelist = readConfig(whitelist, ['whitelist'])
    else:
        mozconfigWhitelist = {}
    log.info("Comparing %s mozconfigs to nightly mozconfigs..." % product)
    success = True
    types = {'+': 'release', '-': 'nightly'}
    for platform,mozconfig in mozconfigs.items():
        urls = []
        mozconfigs = []
        mozconfig_paths = [mozconfig, mozconfig.rstrip('release') + 'nightly']
        # Create links to the two mozconfigs.
        releaseConfig = make_hg_url(hghost, branch, 'http', revision, mozconfig)
        urls.append(releaseConfig)
        # The nightly one is the exact same URL, with the file part changed.
        urls.append(releaseConfig.rstrip('release') + 'nightly')
        for url in urls:
            try:
                mozconfigs.append(urllib2.urlopen(url).readlines())
            except urllib2.HTTPError as e:
                log.error("MISSING: %s - ERROR: %s" % (url, e.msg))
        diffInstance = difflib.Differ()
        if len(mozconfigs) == 2:
            diffList = list(diffInstance.compare(mozconfigs[0],mozconfigs[1]))
            for line in diffList:
                clean_line = line[1:].strip()
                if (line[0] == '-'  or line[0] == '+') and len(clean_line) > 1:
                    # skip comment lines
                    if clean_line.startswith('#'):
                        continue
                    # compare to whitelist
                    if line[0] == '-' and mozconfigWhitelist.get(branch, {}).has_key(platform) \
                        and clean_line in mozconfigWhitelist[branch][platform]:
                            continue
                    if line[0] == '+' and mozconfigWhitelist.get('nightly', {}).has_key(platform) \
                        and clean_line in mozconfigWhitelist['nightly'][platform]:
                            continue
                    message = "found in %s but not in %s: %s"
                    if line[0] == '-':
                        log.error(message % (mozconfig_paths[0], mozconfig_paths[1], clean_line))
                    else:
                        log.error(message % (mozconfig_paths[1], mozconfig_paths[0], clean_line))
                    success = False
                    error_tally.add('verify_mozconfig')
        else:
            log.info("Missing mozconfigs to compare for %s" % platform)
            error_tally.add("verify_mozconfigs: Confirm that %s does not have release/nightly mozconfigs to compare" % platform)
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
                error_tally.add('verify_build')
        except urllib2.HTTPError, inst:
            log.error("cannot find %s. Check again, or -b to bypass" % inst.geturl())
            success = False
            error_tally.add('verify_build')

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
            error_tally.add('verify_configs')
        l10n_changesets = urllib2.urlopen(l10n_url)
        log.info("Comparing tagged revision %s to on-disk %s ..." % (l10n_url, changesets))
        if not compare(l10n_changesets, changesets):
            log.error("local l10n-changesets do not match tagged revisions in repo")
            success = False
            error_tally.add('verify_configs')
    except urllib2.HTTPError:
        log.error("cannot find configs in repo %s" % configs_url)
        log.error("cannot find configs in repo %s" % l10n_url)
        success = False
        error_tally.add('verify_configs')
    return success

def query_locale_revisions(l10n_changesets):
    locales = {}
    if l10n_changesets.endswith('.json'):
        fh = open(l10n_changesets, 'r')
        locales_json = json.load(fh)
        fh.close()
        for locale in locales_json.keys():
            locales[locale] = locales_json[locale]["revision"]
    else:
        for line in open(l10n_changesets, 'r'):
            locale, revision = line.split()
            locales[locale] = revision
    return locales

def verify_l10n_changesets(hgHost, l10n_changesets):
    """Checks for the existance of all l10n changesets"""
    success = True
    locales = query_locale_revisions(l10n_changesets)
    for locale in locales.keys():
        revision = locales[locale]
        localePath = '%(repoPath)s/%(locale)s/file/%(revision)s' % {
            'repoPath': releaseConfig['l10nRepoPath'].strip('/'),
            'locale': locale,
            'revision': revision,
        }
        locale_url = make_hg_url(hgHost, localePath, protocol='https')
        log.info("Checking for existence l10n changeset %s %s in repo %s ..." 
            % (locale, revision, locale_url))
        try:
            urllib2.urlopen(locale_url)
        except urllib2.HTTPError:
            log.error("cannot find l10n locale %s in repo %s" % (locale, locale_url))
            success = False
            error_tally.add('verify_l10n')
    return success

def verify_l10n_dashboard(l10n_changesets):
    """Checks the l10n-changesets against the l10n dashboard"""
    success = True
    locales = query_locale_revisions(l10n_changesets)
    dash_url = 'https://l10n-stage-sj.mozilla.org/shipping/l10n-changesets?ms=%(version)s' % {
        'version': getL10nDashboardVersion(releaseConfig['version'],
                                           releaseConfig['productName']),
    }
    log.info("Comparing l10n changesets on dashboard %s to on-disk %s ..." 
        % (dash_url, l10n_changesets))
    try:
        dash_changesets = {}
        for line in urllib2.urlopen(dash_url):
            locale, revision = line.split()
            dash_changesets[locale] = revision
        for locale in locales:
            revision = locales[locale]
            dash_revision = dash_changesets.pop(locale, None)
            if not dash_revision:
                log.error("\tlocale %s missing on dashboard" % locale)
                success = False
                error_tally.add('verify_l10n_dashboard')
            elif revision != dash_revision:
                log.error("\tlocale %s revisions not matching: %s (config) vs. %s (dashboard)" 
                    % (locale, revision, dash_revision))
                success = False
                error_tally.add('verify_l10n_dashboard')
        for locale in dash_changesets:
            log.error("\tlocale %s missing in config" % locale)
            success = False
            error_tally.add('verify_l10n_dashboard')
    except urllib2.HTTPError:
        log.error("cannot find l10n dashboard at %s" % dash_url)
        success = False
        error_tally.add('verify_l10n_dashboard')
    return success

def verify_l10n_shipped_locales(l10n_changesets, shipped_locales):
    """Ensure that our l10n-changesets on the master match the repo's shipped locales list"""
    success = True
    locales = query_locale_revisions(l10n_changesets)
    log.info("Comparing l10n changesets to shipped locales ...") 
    diff_list = locale_diff(locales, shipped_locales)
    if len(diff_list) > 0:
        log.error("l10n_changesets and shipped_locales differ on locales: %s" % diff_list)
        success = False
        error_tally.add('verify_l10n_shipped_locales')
    return success

def verify_options(cmd_options, config):
    """Check release_configs against command-line opts"""
    success = True
    if cmd_options.version and cmd_options.version != config['version']:
        log.error("version passed in does not match release_configs")
        success = False
        error_tally.add('verify_options')
    if cmd_options.buildNumber and int(cmd_options.buildNumber) != int(config['buildNumber']):
        log.error("buildNumber passed in does not match release_configs")
        success = False
        error_tally.add('verify_options')
    if not getRepoMatchingBranch(cmd_options.branch, config['sourceRepositories']):
        log.error("branch passed in does not exist in release config")
        success = False
        error_tally.add('verify_options')
    return success

if __name__ == '__main__':
    from localconfig import GLOBAL_VARS
    parser = OptionParser(__doc__)
    parser.set_defaults(
            check=True,
            checkL10n=True,
            checkMozconfigs=True,
            dryrun=False,
            username="cltbld",
            loglevel=logging.INFO,
            version=None,
            buildNumber=None,
            branch=None,
            products=None,
            whitelist='../tools/buildbot-helpers/mozconfig_whitelist',
            )
    parser.add_option("-b", "--bypass-check", dest="check", action="store_false",
            help="don't bother verifying release repo's on this master")
    parser.add_option("-l", "--bypass-l10n-check", dest="checkL10n", action="store_false",
            help="don't bother verifying l10n milestones")
    parser.add_option("-m", "--bypass-mozconfig-check", dest="checkMozconfigs", action="store_false",
            help="don't bother verifying mozconfigs")
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
    parser.add_option("-c", "--release-config", dest="releaseConfigFiles",
            action="append",
            help="specify the release-config files (the first is primary)")
    parser.add_option("-p", "--products", dest="products",
            help="coma separated list of products")
    parser.add_option("-w", "--whitelist", dest="whitelist",
            help="whitelist for known mozconfig differences")

    options, args = parser.parse_args()
    if not options.products:
        parser.error("Need to provide a list of products, e.g. -p firefox,fennec")
    if not options.dryrun and not args:
        parser.error("Need to provide a master to sendchange to, or -d for a dryrun")
    elif not options.branch:
        parser.error("Need to provide a branch to release")
    elif not options.releaseConfigFiles:
        parser.error("Need to provide a release config file")

    logging.basicConfig(level=options.loglevel,
            format="%(asctime)s : %(levelname)s : %(message)s")

    releaseConfig = None
    test_success = True
    buildNumber = options.buildNumber
    for releaseConfigFile in list(reversed(options.releaseConfigFiles)):
        releaseConfig = readReleaseConfig(releaseConfigFile)

        if not options.buildNumber:
            log.warn("No buildNumber specified, using buildNumber in release_config, which may be out of date!")
            options.buildNumber = releaseConfig['buildNumber']

        if options.check:
            from config import BRANCHES
            branchConfig = BRANCHES[options.branch]
            #Match command line options to defaults in release_configs
            if not verify_options(options, releaseConfig):
                test_success = False
                log.error("Error verifying command-line options, attempting checking repo")

            # verify that mozconfigs for this release pass diff with nightly, compared to a whitelist
            try:
                path = releaseConfig['sourceRepositories']['mozilla']['path']
                revision = releaseConfig['sourceRepositories']['mozilla']['revision']
            except KeyError:
                try:
                    path = releaseConfig['sourceRepositories']['mobile']['path']
                    revision = releaseConfig['sourceRepositories']['mobile']['revision']
                except:
                    log.error("Can't determine sourceRepo for mozconfigs")
            if options.checkMozconfigs:
                if not verify_mozconfigs(
                        path,
                        revision,
                        branchConfig['hghost'],
                        releaseConfig['productName'],
                        releaseConfig['mozconfigs'],
                        releaseConfig['appName'],
                        options.whitelist
                    ):
                    test_success = False
                    log.error("Error verifying mozconfigs")

            #verify that the release_configs on-disk match the tagged revisions in hg
            if not verify_configs(
                    "%s_BUILD%s" % (releaseConfig['baseTag'], buildNumber),
                    branchConfig['hghost'],
                    GLOBAL_VARS['config_repo_path'],
                    releaseConfig['l10nRevisionFile'],
                    releaseConfigFile,
                    ):
                test_success = False
                log.error("Error verifying configs")

            if options.checkL10n:
                #verify that l10n changesets exist
                if not verify_l10n_changesets(
                        branchConfig['hghost'],
                        releaseConfig['l10nRevisionFile']):
                    test_success = False
                    log.error("Error verifying l10n changesets")

                #verify that l10n changesets match the dashboard
                if not verify_l10n_dashboard(releaseConfig['l10nRevisionFile']):
                    test_success = False
                    log.error("Error verifying l10n dashboard changesets")

                #verify that l10n changesets match the shipped locales in firefox product
                if releaseConfig.get('shippedLocalesPath'):
                    for sr in releaseConfig['sourceRepositories'].values():
                        sourceRepoPath = sr.get('clonePath', sr['path'])
                        shippedLocales = getLocaleListFromShippedLocales(
                                            getShippedLocales(
                                                releaseConfig['productName'],
                                                releaseConfig['appName'],
                                                releaseConfig['version'],
                                                releaseConfig['buildNumber'],
                                                sourceRepoPath,
                                                'http://hg.mozilla.org',
                                                sr['revision'],
                                        ))
                        # l10n_changesets do not have an entry for en-US
                        if 'en-US' in shippedLocales:
                            shippedLocales.remove('en-US')
                        if not verify_l10n_shipped_locales(
                                releaseConfig['l10nRevisionFile'],
                                shippedLocales):
                            test_success = False
                            log.error("Error verifying l10n_changesets matches shipped_locales")

            #verify that the relBranch + revision in the release_configs exists in hg
            for sr in releaseConfig['sourceRepositories'].values():
                sourceRepoPath = sr.get('clonePath', sr['path'])
                if not verify_repo(sourceRepoPath, sr['revision'],
                                   branchConfig['hghost']):
                    test_success = False
                    log.error("Error verifying repos")

            #if this is a respin, verify that the version/milestone files have been bumped
            if buildNumber > 1:
                for sr in releaseConfig['sourceRepositories'].values():
                    if not verify_build(sr, branchConfig['hghost']):
                        test_success = False

    check_buildbot()
    if test_success:
        if not options.dryrun:
            reconfig()
            sourceRepoPath = getRepoMatchingBranch(options.branch, releaseConfig['sourceRepositories'])['path']
            sendchange(
                    sourceRepoPath,
                    "%s_RELEASE" % releaseConfig['baseTag'],
                    options.username,
                    args[0],
                    options.products,
                    )
        else:
            log.info("Tests Passed! Did not run reconfig/sendchange. Rerun without `-d`")
    else:
        log.fatal("Tests Failed! Not running sendchange!")
        log.fatal("Failed tests (run with -b to skip) :")
        for error in error_tally:
            log.fatal(error)
