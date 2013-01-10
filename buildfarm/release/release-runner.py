#!/usr/bin/env python

import site
import time
import datetime
import logging
import sys
import os
from os import path
from optparse import OptionParser
from smtplib import SMTPException
from functools import partial
import textwrap

site.addsitedir(path.join(path.dirname(__file__), "../../lib/python"))

from kickoff.api import Releases, Release, ReleaseL10n
from release.config import substituteReleaseConfig
from release.info import getBaseTag, getTags, readReleaseConfig, \
    getReleaseConfigName, getReleaseTag
from release.versions import getAppVersion
from release.sanity import check_buildbot, sendchange
from util.commands import run_cmd
from util.hg import mercurial, update, commit, tag, apply_and_push, \
    make_hg_url, get_repo_path, cleanOutgoingRevs
from util.retry import retry
from util.fabric.common import check_fabric, FabricHelper
from util.sendmail import sendmail
from util.file import load_config, get_config

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

HG = 'hg.mozilla.org'
RELEASE_SANITY_SCRIPT = path.join(path.dirname(__file__),
                                  "../../buildbot-helpers/release_sanity.py")


def reconfig_warning(from_, to, smtp_server, rr, start_time, elapsed,
                     proc):
    """Called when the buildbot master reconfigs are taking a long time."""
    started = time.strftime("%a, %d %b %Y %H:%M:%S %Z",
                            time.localtime(start_time))
    elapsed = datetime.timedelta(seconds=elapsed)
    subject = "[release-runner] WARNING: Reconfig exceeded %s seconds" % elapsed
    body = textwrap.dedent("""
    A buildbot master reconfig started at %(start_time)s has been running for
    %(elapsed)s seconds without completing.

    - release-runner""" % dict(start_time=started, elapsed=elapsed))
    try:
        for release in rr.new_releases:
            rr.update_status(release, "Waiting on reconfig for %d seconds" % elapsed)
        sendmail(from_=from_, to=to, subject=subject, body=body,
                 smtp_server=smtp_server)
    except SMTPException:
        log.error("Cannot send email", exc_info=True)


class ReleaseRunner(object):
    def __init__(self, api_root=None, username=None, password=None,
                 timeout=60):
        self.new_releases = []
        self.releases_api = Releases((username, password), api_root=api_root,
                                     timeout=timeout)
        self.release_api = Release((username, password), api_root=api_root,
                                   timeout=timeout)
        self.release_l10n_api = ReleaseL10n((username, password),
                                            api_root=api_root, timeout=timeout)

    def get_release_requests(self):
        new_releases = self.releases_api.getReleases()
        if new_releases['releases']:
            self.new_releases = [self.release_api.getRelease(name) for name in
                                 new_releases['releases']]
            return True
        else:
            log.info("No new releases: %s" % new_releases)
            return False

    def get_release_l10n(self, release):
        return self.release_l10n_api.getL10n(release)

    def update_status(self, release, status):
        log.info('updating status for %s to %s' % (release['name'], status))
        self.release_api.updateStatus(release['name'], status)

    def start_release_automation(self, release, master):
        sendchange(
            release['branch'],
            getReleaseTag(getBaseTag(release['product'],
                                     release['version'])),
            release['submitter'],
            master,
            release['product']
        )
        self.mark_as_completed(release)

    def mark_as_completed(self, release):
        log.info('mark as completed %s' % release['name'])
        self.release_api.markAsCompleted(release['name'])


def getPartials(release):
    partials = {}
    for p in release['partials'].split(','):
        partialVersion, buildNumber = p.split('build')
        partials[partialVersion] = {
            'appVersion': getAppVersion(partialVersion),
            'buildNumber': buildNumber,
            'baseTag': getBaseTag(release['product'], partialVersion)
        }
    return partials


def bump_configs(release, cfgFile, l10nContents, workdir, hg_username,
                 productionBranch):
    cfgDir = path.join(workdir, 'mozilla')
    templateFile = path.join(cfgDir, '%s.template' % cfgFile)
    tags = getTags(getBaseTag(release['product'], release['version']),
                   release['buildNumber'])
    cfgFile = path.join(cfgDir, cfgFile)
    l10nChangesetsFile = path.join(
        cfgDir,
        readReleaseConfig(cfgFile)['l10nRevisionFile']
    )
    subs = release.copy()
    if 'partials' in release:
        subs['partials'] = getPartials(release)

    with open(templateFile) as f:
        template = f.read()
    releaseConfig = substituteReleaseConfig(template, **subs)
    # Write out the new configs on default....
    with open(cfgFile, 'w') as f:
        f.write(releaseConfig)
    with open(l10nChangesetsFile, 'w') as f:
        f.write(l10nContents)
    commit(workdir, 'Update release config for %s' % release['name'],
           user=hg_username)

    # And also on whatever the production branch is
    update(workdir, productionBranch)
    with open(cfgFile, 'w') as f:
        f.write(releaseConfig)
    with open(l10nChangesetsFile, 'w') as f:
        f.write(l10nContents)
    prodRev = commit(workdir, 'Update release config for %s' % release['name'],
                     user=hg_username)
    forceTag = False
    if release['buildNumber'] > 1:
        forceTag = True
    tag(workdir, tags, rev=prodRev, force=forceTag, user=hg_username)


def tag_repo(workdir, branch, tags, force, pushRepo, hg_username,
             hg_ssh_key):
    def tag_and_push(repo, attempt):
        update(workdir, branch)
        tag(workdir, tags, rev=branch, force=force, user=hg_username)
        log.info("Tagged %s, attempt #%s" % (repo, attempt))

    apply_and_push(workdir, pushRepo, tag_and_push,
                   ssh_username=hg_username, ssh_key=hg_ssh_key)


def update_and_reconfig(masters_json, callback=None):
    fabric_helper = FabricHelper(masters_json_file=masters_json,
                                 roles=['scheduler', 'build'], subprocess=True,
                                 callback=callback)
    fabric_helper.update_and_reconfig()


def get_release_sanity_args(configs_workdir, release, cfgFile, masters_json,
                            buildbot_configs_branch):
    args = [
        '--branch', path.basename(release['branch']),
        '--username', release['submitter'],
        '--version', release['version'],
        '--build-number', str(release['buildNumber']),
        '--release-config', cfgFile,
        '--skip-verify-configs',
        '--masters-json-file', masters_json,
        '--configs-dir', configs_workdir,
        '--configs-branch', buildbot_configs_branch,
    ]
    if not release['dashboardCheck']:
        args.append('--bypass-l10n-dashboard-check')
    return args

if __name__ == '__main__':
    parser = OptionParser(__doc__)
    parser.add_option('-c', '--config', dest='config',
                      help='Configuration file')

    options = parser.parse_args()[0]

    if not options.config:
        parser.error('Need to pass a config')
    log.info('Loading config from %s' % options.config)
    config = load_config(options.config)

    if config.getboolean('release-runner', 'verbose'):
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    check_buildbot()
    check_fabric()

    sendchange_master = config.get('release-runner', 'sendchange_master')
    if not sendchange_master:
        parser.error('Need to pass sendchange_master')

    # Shorthand
    api_root = config.get('api', 'api_root')
    username = config.get('api', 'username')
    password = config.get('api', 'password')
    hg_username = config.get('release-runner', 'hg_username')
    hg_ssh_key = config.get('release-runner', 'hg_ssh_key')
    buildbot_configs = config.get('release-runner', 'buildbot_configs')
    buildbot_configs_branch = config.get('release-runner',
                                         'buildbot_configs_branch')
    buildbotcustom = config.get('release-runner', 'buildbotcustom')
    buildbotcustom_branch = config.get('release-runner',
                                       'buildbotcustom_branch')
    tools = config.get('release-runner', 'tools')
    tools_branch = config.get('release-runner', 'tools_branch')
    masters_json = config.get('release-runner', 'masters_json')
    staging = config.getboolean('release-runner', 'staging')
    sleeptime = config.getint('release-runner', 'sleeptime')
    notify_from = get_config(config, 'release-runner', 'notify_from', None)
    notify_to = get_config(config, 'release-runner', 'notify_to', None)
    if isinstance(notify_to, basestring):
        notify_to = [x.strip() for x in notify_to.split(',')]
    smtp_server = get_config(config, 'release-runner', 'smtp_server',
                             'localhost')
    configs_workdir = 'buildbot-configs'
    custom_workdir = 'buildbotcustom'
    tools_workdir = 'tools'
    configs_pushRepo = make_hg_url(HG, get_repo_path(buildbot_configs),
                                   protocol='ssh')
    custom_pushRepo = make_hg_url(HG, get_repo_path(buildbotcustom),
                                  protocol='ssh')
    tools_pushRepo = make_hg_url(HG, get_repo_path(tools), protocol='ssh')

    rr = ReleaseRunner(api_root=api_root, username=username, password=password)

    # Main loop waits for new releases, processes them and exits.
    while True:
        log.debug('Fetching release requests')
        new_releases = rr.get_release_requests()
        if rr.new_releases:
            for release in rr.new_releases:
                log.info('Got a new release request: %s' % release)
            break
        else:
            log.debug('Sleeping for %d seconds before polling again' %
                      sleeptime)
            time.sleep(sleeptime)

    # Clean up after any potential previous attempts before starting.
    # Not doing this could end up with multiple heads on the same branch.
    for repo, workdir, push_repo in (
        (buildbot_configs, configs_workdir, configs_pushRepo),
        (buildbotcustom, custom_workdir, custom_pushRepo),
        (tools, tools_workdir, tools_pushRepo)
    ):

        retry(mercurial, args=(repo, workdir))
        cleanOutgoingRevs(workdir, push_repo, hg_username,
                          hg_ssh_key)

    # Create symlinks if needed
    if 'symlinks' in config.sections():
        format_dict = dict(buildbot_configs=configs_workdir,
                           buildbotcustom=custom_workdir, tools=tools_workdir)
        for target in config.options('symlinks'):
            symlink = config.get('symlinks', target).format(**format_dict)
            if path.exists(symlink):
                log.warning("Skipping %s -> %s symlink" % (symlink, target))
            else:
                log.info("Adding %s -> %s symlink" % (symlink, target))
                os.symlink(target, symlink)

    tags = []
    # For safety's sake, we shouldn't force any tagging
    # unless we know we need to.
    force_tag = bool([r for r in rr.new_releases if r['buildNumber'] > 1])

    def process_configs(repo, attempt):
        """Helper method that encapsulates all of the things necessary
           to run release runner for all releases."""
        log.info("Bumping %s, attempt #%s" % (repo, attempt))
        for release in rr.new_releases:
            rr.update_status(release, 'Writing configs')
            l10nContents = rr.get_release_l10n(release['name'])
            tags.extend(getTags(getBaseTag(release['product'],
                                            release['version']),
                                release['buildNumber']))
            update(configs_workdir, revision='default')
            cfgFile = getReleaseConfigName(
                release['product'], path.basename(release['branch']),
                staging)
            bump_configs(release=release, cfgFile=cfgFile,
                            l10nContents=l10nContents,
                            workdir=configs_workdir, hg_username=hg_username,
                            productionBranch=buildbot_configs_branch)
            rr.update_status(release, 'Running release sanity')
            rs_args = get_release_sanity_args(configs_workdir, release,
                                                cfgFile, masters_json,
                                                buildbot_configs_branch)
            run_cmd(['python', RELEASE_SANITY_SCRIPT] + rs_args +
                    ['--dry-run'])
            rr.update_status(
                release, 'Waiting for other releases to run release sanity'
            )

    try:
        # Pushing doesn't happen until _after_ release sanity has been run
        # for all releases to minimize the chance of bad configs being
        # pushed. apply_and_push calls process_configs, and if it returns
        # successfully, it pushes all of the changes that it made.
        apply_and_push(configs_workdir, configs_pushRepo, process_configs,
                       ssh_username=hg_username, ssh_key=hg_ssh_key)

        # Now that we know that all of the configs are good, we can tag
        # the other repositories
        for release in rr.new_releases:
            rr.update_status(release, 'Tagging other repositories')
        tag_repo(workdir=custom_workdir, branch=buildbotcustom_branch,
                    tags=tags, force=force_tag, pushRepo=custom_pushRepo,
                    hg_username=hg_username, hg_ssh_key=hg_ssh_key)
        tag_repo(workdir=tools_workdir, branch=tools_branch, tags=tags,
                    force=force_tag, pushRepo=tools_pushRepo,
                    hg_username=hg_username, hg_ssh_key=hg_ssh_key)
        for release in rr.new_releases:
            rr.update_status(release, 'Reconfiging masters')

        # Reconfig the masters and configure the warning callback, if present.
        callback = None
        if notify_from and notify_to:
            callback = partial(reconfig_warning, notify_from, notify_to,
                               smtp_server, rr)
        update_and_reconfig(masters_json, callback=callback)
    except Exception, e:
        # Rather than catching individual problems and giving very specific
        # status updates to the kickoff application, we use this catch-all.
        # Because nearly all problems require looking at the release runner
        # logs and manual intervention, it's not worth the pain and ugliness
        # to do more than this.
        for release in rr.new_releases:
            rr.update_status(release, 'Failed: %s' % repr(e))
        raise

    rc = 0
    for release in rr.new_releases:
        try:
            rr.update_status(release, 'Running sendchange command')
            rr.start_release_automation(release, sendchange_master)
        except:
            # We explicitly do not raise an error here because there's no
            # reason not to start other releases if the sendchange fails for
            # another one. We _do_ need to set this in order to exit
            # with the right code, though.
            rc = 1
            rr.update_status(release, 'Sendchange failed')
            log.error('Sendchange failed for %s: ' % release, exc_Info=True)

    sys.exit(rc)
