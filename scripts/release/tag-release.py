#!/usr/bin/env python

import logging
from os import path
import sys

sys.path.append(path.join(path.dirname(__file__), "../../lib/python"))
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

from util.commands import run_cmd
from util.hg import clone, apply_and_push, update, get_revision, make_hg_url
from release.info import readReleaseConfig, getTags, generateRelbranchName
from release.l10n import getL10nRepositories

HG="hg.mozilla.org"
VERSION_BUMP_SCRIPT=path.join(path.dirname(sys.argv[0]), "version-bump.pl")
EN_US_BUMP_FILES=['config/milestone.txt', 'js/src/config/milestone.txt',
                  'browser/config/version.txt']
DEFAULT_BUILDBOT_CONFIGS_REPO=make_hg_url(HG, 'build/buildbot-configs')
DEFAULT_MAX_PUSH_ATTEMPTS=10
REQUIRED_CONFIG = ('version', 'appVersion', 'appName', 'productName',
                   'milestone', 'buildNumber', 'hgUsername', 'hgSshKey',
                   'baseTag', 'l10nRepoPath', 'sourceRepoPath',
                   'sourceRepoName', 'sourceRepoRevision', 'l10nRevisionFile')

def getBumpCommitMessage(productName, version):
    return 'Automated checkin: version bump remove "pre" from version number ' \
           'for ' + productName + ' ' + version + \
           ' release. CLOSED TREE a=release'

def getTagCommitMessage(revision, tag):
    return "Added tag " +  tag + " for changeset " + revision + \
           ". CLOSED TREE a=release"

def bump(repo, version, appVersion, appname, productName, milestone,
         buildNumber, bumpFiles, username):
    cmd = ['perl', VERSION_BUMP_SCRIPT, '-w', repo, '-a', appname,
           '-v', appVersion, '-m', milestone]
    cmd.extend(bumpFiles)
    run_cmd(cmd)
    run_cmd(['hg', 'diff'], cwd=repo)
    run_cmd(['hg', 'commit', '-u', username, '-m',
            getBumpCommitMessage(productName, version)],
            cwd=repo)
    return get_revision(repo)

def tag(repo, revision, tags, username):
    for tag in tags:
        cmd = ['hg', 'tag', '-u', username, '-r', revision,
               '-m', getTagCommitMessage(revision, tag), '-f', tag]
        run_cmd(cmd, cwd=repo)

def tagRepo(config, repo, reponame, revision, tags, bumpFiles, relbranch,
            isRelbranchGenerated, pushAttempts):
    clone(make_hg_url(HG, repo), reponame)

    def bump_and_tag(repo, attempt, config, relbranch, isRelbranchGenerated,
                     revision, tags):
        try:
            update(reponame, revision=relbranch)
        except:
            if not isRelbranchGenerated:
                log.error("Couldn't update to required relbranch '%s', fail",
                          relbranch)
                raise Exception("Tagging failed")
            update(reponame, revision=revision)
            run_cmd(['hg', 'branch', relbranch], cwd=reponame)

        if config['buildNumber'] != 1 or len(bumpFiles) == 0:
            log.info("Not bumping anything. buildNumber is " + \
                     str(config['buildNumber']) + " bumpFiles is " + \
                     str(bumpFiles))
        else:
            revision = bump(repo, config['version'], config['appVersion'],
                            config['appName'], config['productName'],
                            config['milestone'], config['buildNumber'],
                            bumpFiles, config['hgUsername'])
        tag(repo, revision, tags, config['hgUsername'])

    apply_and_push(reponame, make_hg_url(HG, repo, protocol='ssh'),
                   lambda r, n: bump_and_tag(r, n, config, relbranch,
                                             isRelbranchGenerated, revision,
                                             tags),
                   pushAttempts, ssh_username=config['hgUsername'],
                   ssh_key=config['hgSshKey'])

def validate(options, args):
    err = False
    config = {}
    if not options.configfile:
        log.info("Must pass --configfile")
        sys.exit(1)
    elif not path.exists(path.join('buildbot-configs', options.configfile)):
        log.info("%s does not exist!" % options.configfile)
        sys.exit(1)

    config = readReleaseConfig(path.join('buildbot-configs', options.configfile))
    for key in REQUIRED_CONFIG:
        if key not in config:
            err = True
            log.info("Required item missing in config: %s" % key)

    if config['buildNumber'] > 1:
        if 'relbranchOverride' not in config or not config['relbranchOverride']:
            err = True
            log.info("relbranchOverride must be provided when buildNumber > 1")
    if err:
        sys.exit(1)
    return config

if __name__ == '__main__':
    from optparse import OptionParser
    import os
    
    parser = OptionParser(__doc__)
    parser.set_defaults(
        attempts=os.environ.get('MAX_PUSH_ATTEMPTS', DEFAULT_MAX_PUSH_ATTEMPTS),
        buildbot_configs=os.environ.get('BUILDBOT_CONFIGS_REPO',
                                        DEFAULT_BUILDBOT_CONFIGS_REPO)
    )
    parser.add_option("-a", "--push-attempts", dest="attempts",
                      help="Number of attempts before giving up on pushing")
    parser.add_option("-c", "--configfile", dest="configfile",
                      help="The release config file to use.")
    parser.add_option("-b", "--buildbot-configs", dest="buildbot_configs",
                      help="The place to clone buildbot-configs from")
    parser.add_option("-t", "--release-tag", dest="release_tag",
                      help="Release tag to update buildbot-configs to")

    options, args = parser.parse_args()
    clone(options.buildbot_configs, 'buildbot-configs')
    update('buildbot-configs', revision=options.release_tag)
    config = validate(options, args)
    configDir = path.dirname(options.configfile)
    
    relbranch = config['relbranchOverride']
    isRelbranchGenerated = False
    if config['buildNumber'] == 1:
        if 'relbranchOverride' not in config or not config['relbranchOverride']:
            relbranch = generateRelbranchName(config['milestone'])
            isRelbranchGenerated = True

    tags = getTags(config['baseTag'], config['buildNumber'])
    l10nRepos = getL10nRepositories(path.join('buildbot-configs', configDir,
                                              config['l10nRevisionFile']),
                                     config['l10nRepoPath'],
                                     relbranch)

    tagRepo(config, config['sourceRepoPath'], config['sourceRepoName'],
            config['sourceRepoRevision'], tags, EN_US_BUMP_FILES,
            relbranch, isRelbranchGenerated, options.attempts)
    failed = []
    for l in sorted(l10nRepos):
        info = l10nRepos[l]
        try:
            tagRepo(config, l, path.basename(l), info['revision'], tags,
                    info['bumpFiles'], relbranch, isRelbranchGenerated,
                    options.attempts)
        # If en-US tags successfully we'll do our best to tag all of the l10n
        # repos, even if some have errors
        except:
            failed.append(l)
    if len(failed) > 0:
        log.info("The following locales failed to tag:")
        for l in failed:
            log.info("  %s" % l)
        sys.exit(1)
