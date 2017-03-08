#!/usr/bin/env python

import logging
import os
from optparse import OptionParser
import site
import yaml

site.addsitedir(os.path.join(os.path.dirname(__file__), "../../lib/python"))

from kickoff import get_partials, ReleaseRunner, make_task_graph_strict_kwargs
from kickoff import get_l10n_config, get_en_US_config
from kickoff import bump_version

from release.versions import getAppVersion
from util.file import load_config, get_config

from taskcluster import Scheduler, Index, Queue
from taskcluster.utils import slugId

log = logging.getLogger(__name__)


def main(release_runner_config, release_config, tc_config):

    api_root = release_runner_config.get('api', 'api_root')
    username = release_runner_config.get('api', 'username')
    password = release_runner_config.get('api', 'password')

    scheduler = Scheduler(tc_config)
    index = Index(tc_config)

    rr = ReleaseRunner(api_root=api_root, username=username, password=password)
    graph_id = slugId()
    log.info('Generating task graph')
    kwargs = {
        # release-runner.ini
        "signing_pvt_key": release_config['signing_pvt_key'],
        "public_key": release_config['docker_worker_key'],
        "balrog_username": release_config['balrog_username'],
        "balrog_password": release_config['balrog_password'],
        "beetmover_aws_access_key_id": release_config['beetmover_aws_access_key_id'],
        "beetmover_aws_secret_access_key": release_config['beetmover_aws_secret_access_key'],
        "signing_class": "release-signing",  # TODO: stagin specific, make them configurable

        # ship-it items
        "version": release_config["version"],
        "revision": release_config["mozilla_revision"],
        "mozharness_changeset": release_config.get("mozharness_changeset") or release_config["mozilla_revision"],
        "buildNumber": release_config["build_number"],
        "l10n_changesets": release_config["l10n_changesets"],

        # was branchConfig items
        "funsize_balrog_api_root": release_config["funsize_balrog_api_root"],
        "balrog_api_root": release_config["balrog_api_root"],
        "build_tools_repo_path": release_config['build_tools_repo_path'],
        "tuxedo_server_url": release_config['tuxedo_server_url'],
        "uptake_monitoring_enabled": release_config['uptake_monitoring_enabled'],
        "beetmover_candidates_bucket": release_config["beetmover_candidates_bucket"],
        "bouncer_enabled": release_config["bouncer_enabled"],
        "updates_builder_enabled": release_config["updates_builder_enabled"],
        "update_verify_enabled": release_config["update_verify_enabled"],
        "push_to_candidates_enabled": release_config['push_to_candidates_enabled'],
        "stage_product": release_config['stage_product'],
        "postrelease_bouncer_aliases_enabled": release_config['postrelease_bouncer_aliases_enabled'],
        "postrelease_version_bump_enabled": release_config['postrelease_version_bump_enabled'],
        "push_to_releases_automatic": release_config['push_to_releases_automatic'],
        "partner_repacks_platforms": release_config["partner_repacks_platforms"],
        "eme_free_repacks_platforms": release_config["eme_free_repacks_platforms"],
        "sha1_repacks_platforms": release_config["sha1_repacks_platforms"],
        "repo_path": release_config["repo_path"],
        "branch": release_config["branch"],
        "product": release_config["product"],
        "release_channels": release_config['channels'],
        "final_verify_channels": release_config['final_verify_channels'],
        "final_verify_platforms": release_config['final_verify_platforms'],
        "uptake_monitoring_platforms": release_config['uptake_monitoring_platforms'],
        "source_enabled": release_config["source_enabled"],
        "checksums_enabled": release_config["checksums_enabled"],
        "updates_enabled": release_config["updates_enabled"],
        "push_to_releases_enabled": release_config["push_to_releases_enabled"],

        "verifyConfigs": {},
        # ESR should not use "esr" suffix here:
        "next_version": bump_version(release_config["version"].replace("esr", "")),
        "appVersion": getAppVersion(release_config["version"]),
        "partial_updates": get_partials(rr, release_config["partials"],
                                        release_config['product']),
        # in release-runner.py world we have a concept of branchConfig and release (shipit) vars
        # todo fix get_en_US_config and en_US_config helper methods to not require both
        "l10n_config": get_l10n_config(
            index=index, product=release_config["product"],
            branch=release_config["branch"],
            revision=release_config["mozilla_revision"],
            platforms=release_config['platforms'],
            l10n_platforms=release_config['l10n_release_platforms'] or {},
            l10n_changesets=release_config["l10n_changesets"],
            tc_task_indexes=None,
        ),
        "en_US_config": get_en_US_config(
            index=index, product=release_config["product"],
            branch=release_config["branch"],
            revision=release_config["mozilla_revision"],
            platforms=release_config['platforms'],
            tc_task_indexes=None,
        ),
        "extra_balrog_submitter_params": release_config['extra_balrog_submitter_params'],
        "publish_to_balrog_channels": release_config["publish_to_balrog_channels"],
        "postrelease_mark_as_shipped_enabled": release_config["postrelease_mark_as_shipped_enabled"],
        # TODO: use [] when snaps_enabled is landed
        "snap_enabled": release_config.get("snap_enabled", False),
        "update_verify_channel": release_config["update_verify_channel"],
        "update_verify_requires_cdn_push": release_config["update_verify_requires_cdn_push"],
    }

    graph = make_task_graph_strict_kwargs(**kwargs)
    log.info("Submitting task graph")
    import pprint
    log.info(pprint.pformat(graph, indent=4, width=160))
    if not options.dry_run:
        print scheduler.createTaskGraph(graph_id, graph)


def get_items_from_common_tc_task(common_task_id, tc_config):
    tc_task_items = {}
    queue = Queue(tc_config)
    task = queue.task(common_task_id)
    tc_task_items["version"] = task["extra"]["build_props"]["version"]
    tc_task_items["build_number"] = task["extra"]["build_props"]["build_number"]
    tc_task_items["mozilla_revision"] = task["extra"]["build_props"]["revision"]
    tc_task_items["partials"] = task["extra"]["build_props"]["partials"]
    tc_task_items["mozharness_changeset"] = task["extra"]["build_props"]["mozharness_changeset"]
    return tc_task_items


def get_unique_release_items(options, tc_config):
    unique_items = {}

    if options.common_task_id:
        # sometimes, we make a release based on a previous release. e.g. a graph that represents
        # part 2 of a Firefox Release Candidate release
        unique_items.update(get_items_from_common_tc_task(options.common_task_id, tc_config))
    else:
        unique_items['version'] = options.version
        unique_items['build_number'] = options.build_number
        unique_items['mozilla_revision'] = options.mozilla_revision
        unique_items['partials'] = options.partials

    # TODO have ability to pass l10n_changesets whether based on previous release or new one
    unique_items["l10n_changesets"] = {}

    return unique_items


def get_release_items_from_runner_config(release_runner_ini):
    ini_items = {}
    ini_items['signing_pvt_key'] = release_runner_ini.get('signing', 'pvt_key')
    ini_items['docker_worker_key'] = release_runner_ini.get('release-runner', 'docker_worker_key')
    ini_items['balrog_username'] = release_runner_ini.get("balrog", "username")
    ini_items['balrog_password'] = release_runner_ini.get("balrog", "password")
    ini_items['beetmover_aws_access_key_id'] = release_runner_ini.get("beetmover", "aws_access_key_id")
    ini_items['beetmover_aws_secret_access_key'] = release_runner_ini.get("beetmover", "aws_secret_access_key")
    ini_items['extra_balrog_submitter_params'] = get_config(release_runner_ini, "balrog",
                                                            "extra_balrog_submitter_params", None)
    return ini_items


def load_branch_and_product_config(config_file):
    with open(config_file, 'r') as rc_file:
        return yaml.load(rc_file)


if __name__ == '__main__':
    parser = OptionParser(__doc__)
    parser.add_option('--release-runner-ini', dest='release_runner_ini',
                      help='ini file that contains things like sensitive credentials')
    parser.add_option('--branch-and-product-config', dest='branch_and_product_config',
                      help='config items specific to certain product and branch')
    parser.add_option('--version', dest='version', help='full version of release, e.g. 46.0b1')
    parser.add_option('--build-number', dest='build_number', help='build number of release')
    parser.add_option('--partials', type="string", dest='partials',
                      help='list of partials for the release')
    parser.add_option('--mozilla-revision', dest='mozilla_revision',
                      help='gecko revision to build ff from')
    parser.add_option('--common-task-id', dest='common_task_id',
                      help='a task id of a task that shares the same release info')
    parser.add_option('--dry-run', dest='dry_run', action='store_true', default=False,
                      help="render the task graph from yaml tmpl but don't submit to taskcluster")

    options = parser.parse_args()[0]

    if not options.release_runner_ini:
        parser.error('Need to pass a release runner config')
    if not options.branch_and_product_config:
        parser.error('Need to pass a branch and product config')

    # load config files
    release_runner_config = load_config(options.release_runner_ini)
    tc_config = {
        "credentials": {
            "clientId": get_config(release_runner_config, "taskcluster", "client_id", None),
            "accessToken": get_config(release_runner_config, "taskcluster", "access_token", None),
        }
    }
    branch_product_config = load_branch_and_product_config(options.branch_and_product_config)

    if release_runner_config.getboolean('release-runner', 'verbose'):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(filename='releasetasks_graph_gen.log',
                        format="%(asctime)s - %(levelname)s - %(message)s",
                        level=log_level)


    # create releasetasks graph args from config files
    releasetasks_kwargs = {}
    releasetasks_kwargs.update(branch_product_config)
    releasetasks_kwargs.update(get_release_items_from_runner_config(release_runner_config))
    releasetasks_kwargs.update(get_unique_release_items(options, tc_config))

    main(release_runner_config, releasetasks_kwargs, tc_config)
