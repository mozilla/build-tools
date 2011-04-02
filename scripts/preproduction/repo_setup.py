#!/usr/bin/env python

import sys
from os import path
import logging
from urllib2 import urlopen, URLError

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(message)s")
log = logging.getLogger(__name__)

sys.path.append(path.join(path.dirname(__file__), "../../lib/python"))
from release.info import readConfig, readReleaseConfig, getTags
from util.commands import run_remote_cmd, run_cmd
from util.hg import make_hg_url, get_repo_name, mercurial, cleanOutgoingRevs, \
     apply_and_push
from util.retry import retry

BUMP_SCRIPT = path.join(path.dirname(__file__), "release_config_bumper.py")


def read_repo_setup_config(configfile):
    log.info('Reading from %s' % configfile)
    return readConfig(configfile, keys=['repoSetupConfig'])


def cat(files):
    content = []
    for f in files:
        content.append(open(f, 'rb').read())
    return ''.join(content)


def recreate_repos(repoSetupConfig):
    hgHost = repoSetupConfig['hgHost']
    repoPath = repoSetupConfig['repoPath']
    hgUserName = repoSetupConfig['hgUserName']
    hgSshKey = path.join(path.expanduser("~"), ".ssh",
                         repoSetupConfig['hgSshKey'])

    for repo in repoSetupConfig['reposToClone'].keys():
        maybe_delete_repo(hgHost, hgUserName, hgSshKey, repo, repoPath)
        clone_repo(hgHost, hgUserName, hgSshKey, repo)

    run_cmd(['sleep', '600'])
    allTags = []

    for repo in repoSetupConfig['reposToClone'].keys():
        if repoSetupConfig['reposToClone'][repo].get('overrides'):
            tags = bump_configs(
                hgHost, hgUserName, hgSshKey, repo, repoPath,
                repoSetupConfig['reposToClone'][repo]['overrides'])
            allTags.extend(tags)
    log.info('Tagging using %s' % ' '. join(allTags))

    for repo in repoSetupConfig['reposToClone'].keys():
        if repoSetupConfig['reposToClone'][repo].get('doTag'):
            tag_repo(hgHost, hgUserName, hgSshKey, repo, repoPath, allTags)


def maybe_delete_repo(server, username, sshKey, repo, repoPath):
    reponame = get_repo_name(repo)
    repo_url = make_hg_url(server, '%s/%s' % (repoPath, reponame))
    try:
        log.info("Trying to open %s" % repo_url)
        urlopen(repo_url)
    except URLError:
        log.info("%s doesn't exist, not deleting" % reponame)
    else:
        log.info('Deleting %s' % reponame)
        retry(run_remote_cmd, args=('edit %s delete YES' % reponame, server,
                                    username, sshKey))


def clone_repo(server, username, sshKey, repo):
    reponame = get_repo_name(repo)
    log.info('Cloning %s to %s' % (repo, reponame))
    retry(run_remote_cmd, args=('clone %s %s' % (reponame, repo),
                        server, username, sshKey))


def bump_configs(server, username, sshKey, repo, repoPath, configsToBump):
    reponame = get_repo_name(repo)
    repo_url = make_hg_url(server, '%s/%s' % (repoPath, reponame))
    pushRepo = make_hg_url(server, '%s/%s' % (repoPath, reponame),
                               protocol='ssh')
    retry(mercurial, args=(repo_url, reponame))

    def bump(repo, configsToBump):
        configs = ['%s/%s' % (repo, x) for x in configsToBump.keys()]
        cmd = ['python', BUMP_SCRIPT, '--bump-version', '--revision=tip']
        cmd.extend(configs)
        run_cmd(cmd)
        for config, overrides in configsToBump.iteritems():
            newContent = cat([path.join(repo, config)] +
                          [path.join(repo, x) for x in overrides])
            fh = open(path.join(repo, config), 'wb')
            fh.write(newContent)
            fh.close()
        run_cmd(['hg', 'commit', '-m', 'Automatic config bump'],
                cwd=repo)

    def bump_wrapper(r, n):
        bump(r, configsToBump)

    def cleanup_wrapper():
        cleanOutgoingRevs(reponame, pushRepo, username, sshKey)

    retry(apply_and_push, cleanup=cleanup_wrapper,
          args=(reponame, pushRepo, bump_wrapper),
          kwargs=dict(ssh_username=username, ssh_key=sshKey))

    tags = []
    for configfile in configsToBump.keys():
        config = readReleaseConfig(path.join(reponame, configfile))
        tags.extend(getTags(config['baseTag'], config['buildNumber'],
                            buildTag=True))
    return tags


def tag_repo(server, username, sshKey, repo, repoPath, tags):
    reponame = get_repo_name(repo)
    repo_url = make_hg_url(server, '%s/%s' % (repoPath, reponame))
    pushRepo = make_hg_url(server, '%s/%s' % (repoPath, reponame),
                               protocol='ssh')
    mercurial(repo_url, reponame)

    def do_tag(repo, tags):
        cmd = ['hg', 'tag', '-f', '-m', 'Automatic preproduction tag'] + tags
        run_cmd(cmd, cwd=repo)

    def do_tag_wrapper(r, n):
        do_tag(r, tags)

    def cleanup_wrapper():
        cleanOutgoingRevs(reponame, pushRepo, username, sshKey)

    retry(apply_and_push, cleanup=cleanup_wrapper,
          args=(reponame, pushRepo, do_tag_wrapper),
          kwargs=dict(ssh_username=username, ssh_key=sshKey))


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(__doc__)

    parser.add_option("-c", "--configfile", dest="configfile")
    options, args = parser.parse_args()

    if not options.configfile:
        parser.error("-c is mandatory")

    repoSetupConfig = read_repo_setup_config(options.configfile)
    recreate_repos(repoSetupConfig)
