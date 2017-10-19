#!/usr/bin/env python
"""
Release runner to schedule action tasks (in-tree scheduling)
"""

import argparse
import logging
import os
import re
import site
import sys
import taskcluster
import time
import yaml

from os import path
from twisted.python.lockfile import FilesystemLock

site.addsitedir(path.join(path.dirname(__file__), "../../lib/python"))

from kickoff import ReleaseRunner, long_revision, email_release_drivers, bump_version
from kickoff.sanity.revisions import RevisionsSanitizer
from kickoff.actions import generate_action_task, submit_action_task


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
    smtp_server = rr_config.get('smtp_server', 'localhost')
    notify_from = rr_config.get('notify_from')
    notify_to = rr_config.get('notify_to_announce')
    if isinstance(notify_to, basestring):
        notify_to = [x.strip() for x in notify_to.split(',')]

    rr = ReleaseRunner(api_root=api_root, username=username, password=password)
    tc_config = {
        "credentials": {
            "clientId": config["taskcluster"].get("client_id"),
            "accessToken": config["taskcluster"].get("access_token"),
        },
        "maxRetries": 12,
    }
    queue = taskcluster.Queue(tc_config)

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
            next_version = bump_version(release["version"].replace("esr", ""))
            action_task_id, action_task = generate_action_task(
                    project=release["branchShortName"],
                    revision=release["mozillaRevision"],
                    next_version=next_version,
                    build_number=release["buildNumber"],
                    release_promotion_flavor="promote_{}".format(release["product"])
            )
            submit_action_task(queue=queue, action_task_id=action_task_id,
                               action_task=action_task)
            rr.mark_as_completed(release)
            l10n_url = rr.release_l10n_api.getL10nFullUrl(release['name'])
            email_release_drivers(smtp_server=smtp_server, from_=notify_from,
                                  to=notify_to, release=release,
                                  task_group_id=action_task_id, l10n_url=l10n_url)
        except Exception as exception:
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
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--lockfile',
                        default=path.join(os.getcwd(), ".release-runner.lock"))
    parser.add_argument('-c', '--config', required=True, help='Configuration file')
    args = parser.parse_args()

    lockfile = args.lockfile
    log.debug("Using lock file %s", lockfile)
    lock = FilesystemLock(lockfile)
    if not lock.lock():
        raise Exception("Cannot acquire lock: %s" % lockfile)
    log.debug("Lock acquired: %s", lockfile)
    if not lock.clean:
        log.warning("Previous run did not properly exit")
    try:
        main(args)
    finally:
        log.debug("Releasing lock: %s", lockfile)
        lock.unlock()
