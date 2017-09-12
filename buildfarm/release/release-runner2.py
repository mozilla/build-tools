#!/usr/bin/env python

import site
import time
import logging
import subprocess
import sys
import os
import re
from os import path
from optparse import OptionParser
from twisted.python.lockfile import FilesystemLock
import yaml

site.addsitedir(path.join(path.dirname(__file__), "../../lib/python"))

from kickoff import ReleaseRunner, long_revision
from kickoff.sanity.revisions import RevisionsSanitizer


log = logging.getLogger(__name__)


def check_and_assign_long_revision(release_runner, release, releases_config):
    # Revisions must be checked before trying to get the long one.
    RevisionsSanitizer(**release).run()
    release['mozillaRevision'] = long_revision(
        release['branch'], release['mozillaRevision'])


def check_allowed_branches(release_runner, release, releases_config):
    product = release['product']
    branch = release['branch']
    for entry in releases_config:
        if entry['product'] == product:
            allowed_branches = entry['allowed_branches']
            for pattern in allowed_branches:
                if re.match(pattern, branch):
                    return
    raise RuntimeError("%s branch not allowed: %s", branch, allowed_branches)


# So people can't run arbitrary functions
CHECKS_MAPPING = {
    'long_revision': check_and_assign_long_revision,
    'check_allowed_branches': check_allowed_branches,
}


def run_prebuild_sanity_checks(release_runner, releases_config):
    new_valid_releases = []

    # results in:
    # { 'firefox': ['long_revision', 'l10n_changesets', 'partial_updates']}
    checks = {r['product'].lower(): r['checks'] for r in releases_config}

    for release in release_runner.new_releases:
        log.info('Got a new release request: %s' % release)
        try:
            # TODO: this won't work for Thunderbird...do we care?
            release['branchShortName'] = release['branch'].split("/")[-1]

            for check in checks[release['product']]:
                if check not in CHECKS_MAPPING:
                    log.error("Check %s not found", check)
                    continue
                CHECKS_MAPPING[check](release_runner, release, releases_config)

            new_valid_releases.append(release)
        except Exception as e:
            release_runner.mark_as_failed(
                release, 'Sanity checks failed. Errors: %s' % e)
            log.exception(
                'Sanity checks failed. Errors: %s. Release: %s', e, release)
    return new_valid_releases


def main(options):
    log.info('Loading config from %s' % options.config)

    with open(options.config, 'r') as config_file:
        config = yaml.load(config_file)

    if config['release-runner'].get('verbose', False):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
                        level=log_level)
    # Suppress logging of retry(), see bug 925321 for the details
    logging.getLogger("util.retry").setLevel(logging.WARN)

    api_root = config['api']['api_root']
    username = config['api']['username']
    password = config['api']['password']

    rr_config = config['release-runner']
    sleeptime = rr_config['sleeptime']

    rr = ReleaseRunner(api_root=api_root, username=username, password=password)

    # Main loop waits for new releases, processes them and exits.
    while True:
        try:
            log.debug('Fetching release requests')
            rr.get_release_requests([r['pattern'] for r in config['releases']])
            if rr.new_releases:
                new_releases = run_prebuild_sanity_checks(
                    rr, config['releases'])
                break
            else:
                log.debug('Sleeping for %d seconds before polling again' %
                          sleeptime)
                time.sleep(sleeptime)
        except:
            log.error("Caught exception when polling:", exc_info=True)
            sys.exit(5)

    rc = 0
    for release in new_releases:
        try:
            relconfigs_tmpl = '{}_{}_fennec_full_graph.yml'.format(rr_config['releasetasks_relconfigs_prefix',
                                                                             release['branchShortName'])
            configs = '/'.join([rr_config['relconfigs_root'], relconfigs_tmpl])

            cmd = [
                rr_config['python'],
                rr_config['gen_script'],
                '--release-runner-config',
                rr_config['release_runner_config'],
                '--branch-and-product-config={}'.format(configs),
                '--version={}'.format(release['version']),
                '--build-number={}'.format(release['buildNumber']),
                '--mozilla-revision={}'.format(release["mozillaRevision"]),
            ]

            rr.update_status(release, 'Generating task graph')

            # TODO: might want to investigate if we can just call a function
            # here instead of the entire script, so that we can send the email
            # directly from this script, and not the gen.py one
            subprocess.check_call(cmd)

            rr.mark_as_completed(release)
            # TODO: normally sending the email should be done here but
            # since we don't have the actual Taskgroup ID, we need to munge
            # the other script to do that
        except subprocess.CalledProcessError as exception:
            # We explicitly do not raise an error here because there's no
            # reason not to start other releases if creating the Task Graph
            # fails for another one. We _do_ need to set this in order to exit
            # with the right code, though.
            rc = 2
            rr.mark_as_failed(
                release,
                'Failed to start release promotion. Error(s): %s' % (exception)
            )
            log.exception('Failed to start release "%s". Error(s): %s',
                          release['name'], exception)
            log.debug('Release failed: %s', release)

    if rc != 0:
        sys.exit(rc)

    log.debug('Sleeping for %s seconds before polling again', sleeptime)
    time.sleep(sleeptime)


if __name__ == '__main__':
    parser = OptionParser(__doc__)
    parser.add_option('-l', '--lockfile', dest='lockfile',
                      default=path.join(os.getcwd(), ".release-runner.lock"))
    parser.add_option('-c', '--config', dest='config',
                      help='Configuration file')

    options = parser.parse_args()[0]

    if not options.config:
        parser.error('Need to pass a config')

    lockfile = options.lockfile
    log.debug("Using lock file %s", lockfile)
    lock = FilesystemLock(lockfile)
    if not lock.lock():
        raise Exception("Cannot acquire lock: %s" % lockfile)
    log.debug("Lock acquired: %s", lockfile)
    if not lock.clean:
        log.warning("Previous run did not properly exit")
    try:
        main(options)
    finally:
        log.debug("Releasing lock: %s", lockfile)
        lock.unlock()
