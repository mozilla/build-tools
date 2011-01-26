#!/usr/bin/env python

import logging
from os import path
from traceback import format_exc
import sys

sys.path.append(path.join(path.dirname(__file__), "../../lib/python"))
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

from util.commands import run_cmd
from util.hg import mercurial, apply_and_push, update, get_revision, \
  make_hg_url, out, BRANCH, REVISION
from build.versions import nextVersion
from release.info import readReleaseConfig, getTags, generateRelbranchName, \
  isFinalRelease
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
    return 'Automated checkin: version bump for ' + productName + ' ' + \
           version + ' release. CLOSED TREE a=release'

def getTagCommitMessage(revision, tag):
    return "Added tag " +  tag + " for changeset " + revision + \
           ". CLOSED TREE a=release"

def bump(repo, version, appVersion, appname, productName, milestone,
         bumpFiles, username):
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
            isRelbranchGenerated, pushAttempts, defaultBranch='default'):
    remote = make_hg_url(HG, repo)
    mercurial(remote, reponame)

    def bump_and_tag(repo, attempt, config, relbranch, isRelbranchGenerated,
                     revision, tags, defaultBranch):
        relbranchChangesets = len(tags)
        if config['buildNumber'] == 1 and len(bumpFiles) > 0:
            shouldBump = True
            relbranchChangesets += 1
            defaultBranchChangesets = 1
        else:
            shouldBump = False
            defaultBranchChangesets = 0

        try:
            update(reponame, revision=relbranch)
        except:
            if not isRelbranchGenerated:
                log.error("Couldn't update to required relbranch '%s', fail",
                          relbranch)
                raise Exception("Tagging failed")
            update(reponame, revision=revision)
            run_cmd(['hg', 'branch', relbranch], cwd=reponame)

        if shouldBump:
            # This is the bump of the version on the release branch
            revision = bump(repo, config['version'], config['appVersion'],
                            config['appName'], config['productName'],
                            config['milestone'], bumpFiles,
                            config['hgUsername'])
        else:
            log.info("Not bumping anything. buildNumber is " + \
                     str(config['buildNumber']) + " bumpFiles is " + \
                     str(bumpFiles))
        tag(repo, revision, tags, config['hgUsername'])
        if shouldBump:
            # This is the bump of the version on the default branch
            # We do it after the other one in order to get the tip of the
            # repository back on default, thus avoiding confusion.
            update(reponame, revision=defaultBranch)
            bump(repo, config['version'], 
                 nextVersion(config['appVersion'], pre=True), config['appName'],
                 config['productName'],
                 nextVersion(config['milestone'], pre=True), bumpFiles,
                 config['hgUsername'])
        # Validate that the repository is only different from the remote in
        # ways we expect.
        outgoingRevs = out(src=reponame, remote=remote,
                           ssh_username=config['hgUsername'],
                           ssh_key=config['hgSshKey'])
        if len([r for r in outgoingRevs if r[BRANCH] == "default"]) != defaultBranchChangesets:
            raise Exception("Incorrect number of revisions on 'default' branch")
        if len([r for r in outgoingRevs if r[BRANCH] == relbranch]) != relbranchChangesets:
            raise Exception("Incorrect number of revisions on %s" % relbranch)
        if len(outgoingRevs) != (relbranchChangesets + defaultBranchChangesets):
            raise Exception("Wrong number of outgoing revisions")

    try:
        apply_and_push(reponame, make_hg_url(HG, repo, protocol='ssh'),
                       lambda r, n: bump_and_tag(r, n, config, relbranch,
                                                 isRelbranchGenerated, revision,
                                                 tags, defaultBranch),
                       pushAttempts, ssh_username=config['hgUsername'],
                       ssh_key=config['hgSshKey'])
    except:
        outgoingRevs = out(src=reponame, remote=remote,
                           ssh_username=config['hgUsername'],
                           ssh_key=config['hgSshKey'])
        for r in reversed(outgoingRevs):
            run_cmd(['hg', 'strip', r[REVISION]], cwd=reponame)
        raise

def tagOtherRepo(config, repo, reponame, revision, pushAttempts):
    remote = make_hg_url(HG, repo)
    mercurial(remote, reponame)

    def tagRepo(repo, attempt, config, revision, tags):
        totalChangesets = len(tags)
        tag(repo, revision, tags, config['hgUsername'])
        outgoingRevs = out(src=reponame, remote=remote,
                           ssh_username=config['hgUsername'],
                           ssh_key=config['hgSshKey'])
        if len(outgoingRevs) != totalChangesets:
            raise Exception("Wrong number of outgoing revisions")
    
    try:
        apply_and_push(reponame, make_hg_url(HG, repo, protocol='ssh'),
                       lambda r, n: tagRepo(r, n, config, revision, tags),
                       pushAttempts, ssh_username=config['hgUsername'],
                       ssh_key=config['hgSshKey'])
    except:
        outgoingRevs = out(src=reponame, remote=remote,
                           ssh_username=config['hgUsername'],
                           ssh_key=config['hgSshKey'])
        for r in reversed(outgoingRevs):
            run_cmd(['hg', 'strip', r[REVISION]], cwd=reponame)
        raise

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
    if 'otherReposToTag' in config:
        if not callable(getattr(config['otherReposToTag'], 'iteritems')):
            err = True
            log.info("otherReposToTag exists in config but is not a dict")
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
                                        DEFAULT_BUILDBOT_CONFIGS_REPO),
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
    mercurial(options.buildbot_configs, 'buildbot-configs')
    update('buildbot-configs', revision=options.release_tag)
    config = validate(options, args)
    configDir = path.dirname(options.configfile)
    
    relbranch = config['relbranchOverride']
    isRelbranchGenerated = False
    if config['buildNumber'] == 1:
        if 'relbranchOverride' not in config or not config['relbranchOverride']:
            relbranch = generateRelbranchName(config['milestone'])
            isRelbranchGenerated = True
    if isFinalRelease(config['version']):
        buildTag = False
        enUSBumpFiles = []
    else:
        buildTag = True
        enUSBumpFiles = EN_US_BUMP_FILES

    tags = getTags(config['baseTag'], config['buildNumber'], buildTag=buildTag)
    l10nRepos = getL10nRepositories(path.join('buildbot-configs', configDir,
                                              config['l10nRevisionFile']),
                                     config['l10nRepoPath'],
                                     relbranch)

    tagRepo(config, config['sourceRepoPath'], config['sourceRepoName'],
            config['sourceRepoRevision'], tags, enUSBumpFiles,
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
            failed.append((l, format_exc()))
    if 'otherReposToTag' in config:
        for repo, revision in config['otherReposToTag'].iteritems():
            try:
                tagOtherRepo(config, repo, path.basename(repo), revision,
                             options.attempts)
            except:
                failed.append((repo, format_exc()))
    if len(failed) > 0:
        log.info("The following locales failed to tag:")
        for l,e in failed:
            log.info("  %s" % l)
            log.info("%s\n" % e)
        sys.exit(1)
