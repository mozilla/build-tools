#!/usr/bin/env python

import os
from os import path
import sys
import logging
from subprocess import CalledProcessError
from tempfile import NamedTemporaryFile
import site

logging.basicConfig(
    stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

site.addsitedir(path.join(path.dirname(__file__), "../../lib/python"))
site.addsitedir(path.join(path.dirname(__file__), "../../lib/python/vendor"))
from release.info import readReleaseConfig, readBranchConfig, readConfig
from release.paths import makeCandidatesDir, makeReleasesDir
from util.hg import update, make_hg_url, mercurial
from util.commands import run_remote_cmd
from util.transfer import scp
from util.retry import retry
import requests


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
                          '--exclude=*.checksums.asc',
                          '--exclude=logs',
                          '--exclude=jsshell*',
                          '--exclude=host',
                          '--exclude=*.json',
                          '--exclude=*mar-tools*',
                          ]

VIRUS_SCAN_CMD = ['nice', 'ionice', '-c2', '-n7',
                  'extract_and_run_command.py', '-j2', 'clamdscan', '-m',
                  '--no-summary', '--']

PARTNER_BUNDLE_DIR = '/mnt/netapp/stage/releases.mozilla.com/bundles'
# Left side is destination relative to PARTNER_BUNDLE_DIR.
# Right side is source, relative to partner-repacks in the candidates dir.
PARTNER_BUNDLE_MAPPINGS = {
    r'msn/international/mac/australia/Firefox\ Setup.dmg': r'msn-australia/mac/en-US/Firefox\ %(version)s.dmg',
    r'msn/international/mac/canada/Firefox\ Setup.dmg': r'msn-canada/mac/en-US/Firefox\ %(version)s.dmg',
    r'msn/international/mac/de/Firefox\ Setup.dmg': r'msn-de/mac/de/Firefox\ %(version)s.dmg',
    r'msn/international/mac/en-GB/Firefox\ Setup.dmg': r'msn-uk/mac/en-GB/Firefox\ %(version)s.dmg',
    r'msn/international/mac/fr/Firefox\ Setup.dmg': r'msn-fr/mac/fr/Firefox\ %(version)s.dmg',
    r'msn/international/mac/ja/Firefox\ Setup.dmg': r'msn-ja/mac/ja-JP-mac/Firefox\ %(version)s.dmg',
    r'msn/us/mac/en-US/Firefox\ Setup.dmg': r'msn-us/mac/en-US/Firefox\ %(version)s.dmg',
    r'bing/mac/en-US/Firefox-Bing.dmg': r'bing/mac/en-US/Firefox\ %(version)s.dmg',
    r'msn/international/win32/australia/Firefox\ Setup.exe': r'msn-australia/win32/en-US/Firefox\ Setup\ %(version)s.exe',
    r'msn/international/win32/canada/Firefox\ Setup.exe': r'msn-canada/win32/en-US/Firefox\ Setup\ %(version)s.exe',
    r'msn/international/win32/de/Firefox\ Setup.exe': r'msn-de/win32/de/Firefox\ Setup\ %(version)s.exe',
    r'msn/international/win32/en-GB/Firefox\ Setup.exe': r'msn-uk/win32/en-GB/Firefox\ Setup\ %(version)s.exe',
    r'msn/international/win32/fr/Firefox\ Setup.exe': r'msn-fr/win32/fr/Firefox\ Setup\ %(version)s.exe',
    r'msn/international/win32/ja/Firefox\ Setup.exe': r'msn-ja/win32/ja/Firefox\ Setup\ %(version)s.exe',
    r'msn/us/win32/en-US/Firefox\ Setup.exe': r'msn-us/win32/en-US/Firefox\ Setup\ %(version)s.exe',
    r'bing/win32/en-US/Firefox-Bing\ Setup.exe': r'bing/win32/en-US/Firefox\ Setup\ %(version)s.exe',
}


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
    sourceRepoName = releaseConfig['sourceRepositories'][
        options.sourceRepoKey]['name']
    branchConfig = readBranchConfig(branchConfigDir, branchConfigFile,
                                    sourceRepoName,
                                    required=REQUIRED_BRANCH_CONFIG)
    return branchConfig, releaseConfig


def checkStagePermissions(productName, version, buildNumber, stageServer,
                          stageUsername, stageSshKey):
    # The following commands should return 0 lines output and exit code 0
    tests = ["find %%s ! -user %s ! -path '*/contrib*'" % stageUsername,
             "find %%s ! -group `id -g -n %s` ! -path '*/contrib*'" % stageUsername,
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
                  extra_excludes=None, dryRun=False, overwrite=False):
    """ excludes overrides DEFAULT_RSYNC_EXCLUDES, extra_exludes will be
    appended to DEFAULT_RSYNC_EXCLUDES. """

    source_dir = makeCandidatesDir(productName, version, buildNumber)
    target_dir = makeReleasesDir(productName, version)

    if not excludes:
        excludes = DEFAULT_RSYNC_EXCLUDES
    if extra_excludes:
        excludes += ['--exclude=%s' % ex for ex in extra_excludes]

    # fail/warn if target directory exists depending on dry run mode
    try:
        run_remote_cmd(['test', '!', '-d', target_dir], server=stageServer,
                       username=stageUsername, sshKey=stageSshKey)
    except CalledProcessError:
        if overwrite:
            log.info('target directory %s exists, but overwriting files as requested' % target_dir)
        elif dryRun:
            log.warning('WARN: target directory %s exists', target_dir)
        else:
            raise

    if not dryRun:
        run_remote_cmd(['mkdir', '-p', target_dir], server=stageServer,
                       username=stageUsername, sshKey=stageSshKey)
        run_remote_cmd(
            ['chmod', 'u=rwx,g=rxs,o=rx', target_dir], server=stageServer,
            username=stageUsername, sshKey=stageSshKey)
    rsync_cmd = ['rsync', '-av']
    if dryRun:
        rsync_cmd.append('-n')
    run_remote_cmd(rsync_cmd + excludes + [source_dir, target_dir],
                   server=stageServer, username=stageUsername,
                   sshKey=stageSshKey)


indexFileTemplate = """\
<!DOCTYPE html>
<html><head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
<style media="all">@import "http://www.mozilla.org/style/firefox/4.0beta/details.css";</style>
<title>Thanks for your interest in Firefox %(version)s</title>
</head>
<body>
<h1>Thanks for your interest in Firefox %(version)s</h1>
<p>We aren't quite finished qualifying Firefox %(version)s yet. You should check out the latest <a href="http://www.mozilla.org/firefox/channel">Beta</a>.</p>
<p>When we're all done with Firefox %(version)s it will show up on <a href="http://firefox.com?ref=ftp">Firefox.com</a>.</p>
</body>
</html>"""


def makeIndexFiles(productName, version, buildNumber, stageServer,
                   stageUsername, stageSshKey):
    candidates_dir = makeCandidatesDir(productName, version, buildNumber)
    indexFile = NamedTemporaryFile()
    indexFile.write(indexFileTemplate % {'version': version})
    indexFile.flush()

    scp(
        indexFile.name, '%s@%s:%s/index.html' % (
            stageUsername, stageServer, candidates_dir),
        sshKey=stageSshKey)
    run_remote_cmd(['chmod', '644', '%s/index.html' % candidates_dir],
                   server=stageServer, username=stageUsername, sshKey=stageSshKey)
    run_remote_cmd(
        ['find', candidates_dir, '-mindepth', '1', '-type', 'd', '-not', '-regex', '.*contrib.*', '-exec', 'cp', '-pv', '%s/index.html' % candidates_dir, '{}', '\\;'],
        server=stageServer, username=stageUsername, sshKey=stageSshKey)


def deleteIndexFiles(cleanup_dir, stageServer, stageUsername,
                     stageSshKey):
    run_remote_cmd(
        ['find', cleanup_dir, '-name', 'index.html', '-exec', 'rm',
            '-v', '{}', '\\;'],
        server=stageServer, username=stageUsername, sshKey=stageSshKey)


def updateSymlink(productName, version, stageServer, stageUsername,
                  stageSshKey, target):
    releases_dir = makeReleasesDir(productName)

    run_remote_cmd([
        'cd %(rd)s && rm -f %(target)s && ln -s %(version)s %(target)s' %
        dict(rd=releases_dir, version=version, target=target)],
        server=stageServer, username=stageUsername, sshKey=stageSshKey)


def doSyncPartnerBundles(productName, version, buildNumber, stageServer,
                         stageUsername, stageSshKey):
    candidates_dir = makeCandidatesDir(productName, version, buildNumber)

    for dest, src in PARTNER_BUNDLE_MAPPINGS.iteritems():
        full_dest = path.join(PARTNER_BUNDLE_DIR, dest)
        full_src = path.join(candidates_dir, 'partner-repacks', src)
        full_src = full_src % {'version': version}
        run_remote_cmd(['cp', '-f', full_src, full_dest],
            server=stageServer, username=stageUsername, sshKey=stageSshKey
        )

    # And fix the permissions...
    run_remote_cmd(
        ['find', PARTNER_BUNDLE_DIR, '-type', 'd',
         '-exec', 'chmod', '775', '{}', '\\;'],
        server=stageServer, username=stageUsername, sshKey=stageSshKey
    )
    run_remote_cmd(
        ['find', PARTNER_BUNDLE_DIR, '-name', '"*.exe"',
         '-exec', 'chmod', '775', '{}', '\\;'],
        server=stageServer, username=stageUsername, sshKey=stageSshKey
    )
    run_remote_cmd(
        ['find', PARTNER_BUNDLE_DIR, '-name', '"*.dmg"',
         '-exec', 'chmod', '775', '{}', '\\;'],
        server=stageServer, username=stageUsername, sshKey=stageSshKey
    )


def update_bouncer_aliases(tuxedoServerUrl, auth, version, bouncer_aliases):
    for related_product_template, alias in bouncer_aliases.iteritems():
        update_bouncer_alias(tuxedoServerUrl, auth, version,
                             related_product_template, alias)


def update_bouncer_alias(tuxedoServerUrl, auth, version,
                         related_product_template, alias):
    url = "%s/create_update_alias" % tuxedoServerUrl
    related_product = related_product_template % {"version": version}

    data = {"alias": alias, "related_product": related_product}
    log.info("Updating %s to point to %s using %s", alias, related_product,
             url)

    # Wrap the real call to hide credentials from retry's logging
    def do_update_bouncer_alias():
        requests.post(url, data=data, auth=auth, config={'danger_mode': True},
                      verify=False)

    retry(do_update_bouncer_alias)


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
    parser.add_option("--product", dest="product")
    parser.add_option("--ssh-user", dest="ssh_username")
    parser.add_option("--ssh-key", dest="ssh_key")
    parser.add_option("--overwrite", dest="overwrite", default=False, action="store_true")
    parser.add_option("--extra-excludes", dest="extra_excludes",
                      action="append")

    options, args = parser.parse_args()
    mercurial(options.buildbotConfigs, "buildbot-configs")
    update("buildbot-configs", revision=options.releaseTag)

    branchConfig, releaseConfig = validate(options, args)

    productName = options.product or releaseConfig['productName']
    version = releaseConfig['version']
    buildNumber = releaseConfig['buildNumber']
    stageServer = branchConfig['stage_server']
    stageUsername = options.ssh_username or branchConfig['stage_username']
    stageSshKey = options.ssh_key or branchConfig["stage_ssh_key"]
    stageSshKey = path.join(os.path.expanduser("~"), ".ssh", stageSshKey)
    createIndexFiles = releaseConfig.get('makeIndexFiles', False) \
        and productName != 'xulrunner'
    syncPartnerBundles = releaseConfig.get('syncPartnerBundles', False) \
        and productName != 'xulrunner'
    ftpSymlinkName = releaseConfig.get('ftpSymlinkName')
    bouncer_aliases = releaseConfig.get('bouncer_aliases')

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
                      extra_excludes=options.extra_excludes,
                      dryRun=True)

    if 'push' in args:
        if createIndexFiles:
            makeIndexFiles(stageServer=stageServer,
                           stageUsername=stageUsername,
                           stageSshKey=stageSshKey,
                           productName=productName,
                           version=version,
                           buildNumber=buildNumber)
        pushToMirrors(stageServer=stageServer,
                      stageUsername=stageUsername,
                      stageSshKey=stageSshKey,
                      productName=productName,
                      version=version,
                      extra_excludes=options.extra_excludes,
                      buildNumber=buildNumber,
                      overwrite=options.overwrite)
        if createIndexFiles:
            deleteIndexFiles(stageServer=stageServer,
                             stageUsername=stageUsername,
                             stageSshKey=stageSshKey,
                             cleanup_dir=makeCandidatesDir(productName, version, buildNumber))

    if 'postrelease' in args:
        if createIndexFiles:
            deleteIndexFiles(stageServer=stageServer,
                             stageUsername=stageUsername,
                             stageSshKey=stageSshKey,
                             cleanup_dir=makeReleasesDir(productName, version))
        if ftpSymlinkName:
            updateSymlink(stageServer=stageServer,
                          stageUsername=stageUsername,
                          stageSshKey=stageSshKey,
                          productName=productName,
                          version=version,
                          target=ftpSymlinkName)
        if syncPartnerBundles:
            doSyncPartnerBundles(stageServer=stageServer,
                                 stageUsername=stageUsername,
                                 stageSshKey=stageSshKey,
                                 productName=productName,
                                 version=version,
                                 buildNumber=buildNumber)
        if bouncer_aliases and productName != 'xulrunner':
            credentials_file = path.join(os.getcwd(), "oauth.txt")
            credentials = readConfig(
                credentials_file,
                required=["tuxedoUsername", "tuxedoPassword"])
            auth = (credentials["tuxedoUsername"],
                    credentials["tuxedoPassword"])

            update_bouncer_aliases(
                tuxedoServerUrl=releaseConfig["tuxedoServerUrl"],
                auth=auth,
                version=version,
                bouncer_aliases=bouncer_aliases)
