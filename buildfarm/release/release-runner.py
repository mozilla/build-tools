#!/usr/bin/env python

import site
import time
import logging
import sys
import os
import re
import subprocess
import hashlib
import functools
import shutil
import tempfile
import requests
from os import path
from optparse import OptionParser
from twisted.python.lockfile import FilesystemLock

site.addsitedir(path.join(path.dirname(__file__), "../../lib/python"))

from kickoff.api import Releases, Release, ReleaseL10n
from release.info import readBranchConfig
from release.l10n import parsePlainL10nChangesets
from release.versions import getAppVersion
from releasetasks import make_task_graph
from taskcluster import Scheduler, Index, Queue
from taskcluster.utils import slugId
from util.hg import mercurial
from util.retry import retry
from util.file import load_config, get_config
from util.sendmail import sendmail

log = logging.getLogger(__name__)


# both CHECKSUMS and ALL_FILES have been defined to improve the release sanity
# en-US binaries timing by whitelisting artifacts of interest - bug 1251761
CHECKSUMS = set([
    '.checksums',
    '.checksums.asc',
])


ALL_FILES = set([
    '.checksums',
    '.checksums.asc',
    '.complete.mar',
    '.exe',
    '.dmg',
    'i686.tar.bz2',
    'x86_64.tar.bz2',
])


# temporary regex to filter out anything but firefox beta releases within
# release promotion. Once migration from buildbot to promotion is completed
# for all types of releases, we will backout this filtering  - bug 1252333
RELEASE_PATTERNS = [
    r"Firefox-\d+\.0b\d+-build\d+"
]


class SanityException(Exception):
    pass


# FIXME: the following function should be removed and we should use
# next_version provided by ship-it
def bump_version(version):
    """Bump last digit"""
    split_by = "."
    digit_index = 2
    if "b" in version:
        split_by = "b"
        digit_index = 1
    v = version.split(split_by)
    if len(v) < digit_index + 1:
        # 45.0 is 45.0.0 actually
        v.append("0")
    v[-1] = str(int(v[-1]) + 1)
    return split_by.join(v)


def matches(name, patterns):
    return any([re.search(p, name) for p in patterns])

def is_candidate_release(channels):
    """determine if this is a candidate release or not

    Because ship-it can not tell us if this is a candidate release (yet!), we assume it is when we
    have determined, based on version, that we are planning to ship to more than one update_channel
    e.g. for candidate releases we have:
     1) one channel to test the 'candidate' release with: to 'beta' channel users
     2) once verified, we ship to the main channel: to 'release' channel users
    """
    return len(channels) > 1

def update_channels(version, mappings):
    """Return a list of update channels for a version using version mapping

    >>> update_channels("40.0", [(r"^\d+\.0$", ["beta", "release"]), (r"^\d+\.\d+\.\d+$", ["release"])])
    ["beta", "release"]
    >>> update_channels("40.0.1", [(r"^\d+\.0$", ["beta", "release"]), (r"^\d+\.\d+\.\d+$", ["release"])])
    ["release"]

    """
    for pattern, channels in mappings:
        if re.match(pattern, version):
            return channels
    raise RuntimeError("Cannot find update channels for %s" % version)


def get_display_version(repo_path, revision):
    """Get display version from remote repository

    >>> get_display_version("releases/mozilla-beta", "59f372c35b24")
    '46.0b3'

    >>> get_display_version("releases/mozilla-beta", "59f372c35b2416ac84d6572d64c49227481a8a6c")
    '46.0b3'
    """
    # The location is the same for both Firefox and Fennec
    url = "https://hg.mozilla.org/{repo_path}/raw-file/{revision}/browser/config/version_display.txt"
    url = url.format(repo_path=repo_path, revision=revision)

    def _get():
        req = requests.get(url, timeout=60)
        req.raise_for_status()
        return req.content.strip()

    return retry(_get)


def long_revision(repo, revision):
    """Convert short revision to long using JSON API

    >>> long_revision("releases/mozilla-beta", "59f372c35b24")
    u'59f372c35b2416ac84d6572d64c49227481a8a6c'

    >>> long_revision("releases/mozilla-beta", "59f372c35b2416ac84d6572d64c49227481a8a6c")
    u'59f372c35b2416ac84d6572d64c49227481a8a6c'
    """
    url = "https://hg.mozilla.org/{}/json-rev/{}".format(repo, revision)

    def _get():
        req = requests.get(url, timeout=60)
        req.raise_for_status()
        return req.json()["node"]

    return retry(_get)


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
            new_releases = [self.release_api.getRelease(name) for name in
                            new_releases['releases']]
            our_releases = [r for r in new_releases if
                            matches(r['name'], RELEASE_PATTERNS)]
            if our_releases:
                # make sure to use long revision
                for r in our_releases:
                    r["mozillaRevision"] = long_revision(r["branch"], r["mozillaRevision"])
                self.new_releases = our_releases
                log.info("Releases to handle are %s", self.new_releases)
                return True
            else:
                log.info("No releases to handle in %s", new_releases)
                return False
        else:
            log.info("No new releases: %s" % new_releases)
            return False

    def get_release_l10n(self, release):
        return self.release_l10n_api.getL10n(release)

    def update_status(self, release, status):
        log.info('updating status for %s to %s' % (release['name'], status))
        try:
            self.release_api.update(release['name'], status=status)
        except requests.HTTPError, e:
            log.warning('Caught HTTPError: %s' % e.response.content)
            log.warning('status update failed, continuing...', exc_info=True)

    def mark_as_completed(self, release):#, enUSPlatforms):
        log.info('mark as completed %s' % release['name'])
        self.release_api.update(release['name'], complete=True,
                                status='Started')

    def mark_as_failed(self, release, why):
        log.info('mark as failed %s' % release['name'])
        self.release_api.update(release['name'], ready=False, status=why)


def getPartials(release):
    partials = {}
    for p in release['partials'].split(','):
        partialVersion, buildNumber = p.split('build')
        partials[partialVersion] = {
            'appVersion': getAppVersion(partialVersion),
            'buildNumber': buildNumber,
        }
    return partials


def email_release_drivers(smtp_server, from_, to, release, graph_id):
    # Send an email to the mailing after the build

    content = """\
A new build has been submitted through ship-it:

Commit: https://hg.mozilla.org/{path}/rev/{revision}
Task graph: https://tools.taskcluster.net/task-graph-inspector/#{task_graph_id}/

Created by {submitter}
Started by {starter}


""".format(path=release["branch"], revision=release["mozillaRevision"],
           submitter=release["submitter"], starter=release["starter"],
           task_graph_id=graph_id)

    comment = release.get("comment")
    if comment:
        content += "Comment:\n" + comment + "\n\n"

    # On r-d, we prefix the subject of the email in order to simplify filtering
    if "Fennec" in release["name"]:
        subject_prefix = "[mobile] "
    if "Firefox" in release["name"]:
        subject_prefix = "[desktop] "

    subject = subject_prefix + 'Build of %s' % release["name"]

    sendmail(from_=from_, to=to, subject=subject, body=content,
             smtp_server=smtp_server)


def get_platform_locales(l10n_changesets, platform):
    # hardcode ja/ja-JP-mac exceptions
    if platform == "macosx64":
        ignore = "ja"
    else:
        ignore = "ja-JP-mac"

    return [l for l in l10n_changesets.keys() if l != ignore]


def get_l10n_config(release, branchConfig, branch, l10n_changesets, index):
    l10n_platforms = {}
    for platform in branchConfig["l10n_release_platforms"]:
        task = index.findTask("buildbot.revisions.{revision}.{branch}.{platform}".format(
            revision=release["mozillaRevision"],
            branch=branch,
            platform=platform,
        ))
        url = "https://queue.taskcluster.net/v1/task/{taskid}/artifacts/public/build".format(
            taskid=task["taskId"]
        )
        l10n_platforms[platform] = {
            "locales": get_platform_locales(l10n_changesets, platform),
            "en_us_binary_url": url,
            "chunks": branchConfig["platforms"][platform].get("l10n_chunks", 10),
        }

    return {
        "platforms": l10n_platforms,
        "changesets": l10n_changesets,
    }


def get_en_US_config(release, branchConfig, branch, index):
    platforms = {}
    for platform in branchConfig["release_platforms"]:
        task = index.findTask("buildbot.revisions.{revision}.{branch}.{platform}".format(
            revision=release["mozillaRevision"],
            branch=branch,
            platform=platform,
        ))
        platforms[platform] = {
            "task_id": task["taskId"],
        }

    return {
        "platforms": platforms,
    }


def validate_version(repo_path, revision, version):
    actual_version = get_display_version(repo_path, revision)
    if version != actual_version:
        raise SanityException(
            "In-tree version '%s' doesn't match ship-it version '%s'" %
            (actual_version, version))
    else:
        log.info("In-tree version '%s' matches ship-it version '%s'",
                 actual_version, version)


def validate_signatures(checksums, signature, dir_path, gpg_key_path):
    try:
        cmd = ['gpg', '--batch', '--homedir', dir_path, '--import',
               gpg_key_path]
        subprocess.check_call(cmd)
        cmd = ['gpg', '--homedir', dir_path, '--verify', signature, checksums]
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        log.exception("GPG signature check failed")
        raise SanityException("GPG signature check failed")


def parse_sha512(checksums, files):
    # parse the checksums file and store all sha512 digests
    _dict = dict()
    with open(checksums, 'rb') as fd:
        lines = fd.readlines()
        for line in lines:
            digest, alg, _, name = line.split()
            if alg != 'sha512':
                continue
            _dict[os.path.basename(name)] = digest
    wdict = {k: _dict[k] for k in _dict.keys() if file_in_whitelist(k, files)}
    return wdict


def download_all_artifacts(queue, artifacts, task_id, dir_path):
    failed_downloads = False

    for artifact in artifacts:
        name = os.path.basename(artifact)
        build_url = queue.buildSignedUrl(
            'getLatestArtifact',
            task_id,
            artifact
        )
        log.debug('Downloading %s', name)
        try:
            r = requests.get(build_url, timeout=60)
            r.raise_for_status()
        except requests.HTTPError:
            log.exception("Failed to download %s", name)
            failed_downloads = True
        else:
            filepath = os.path.join(dir_path, name)
            with open(filepath, 'wb') as fd:
                for chunk in r.iter_content(1024):
                    fd.write(chunk)

    if failed_downloads:
        raise SanityException('Downloading artifacts failed')


def validate_checksums(_dict, dir_path):
    for name in _dict.keys():
        filepath = os.path.join(dir_path, name)
        computed_hash = get_hash(filepath)
        correct_hash = _dict[name]
        if computed_hash != correct_hash:
            log.error("failed to validate checksum for %s", name, exc_info=True)
            raise SanityException("Failed to check digest for %s" % name)


def file_in_whitelist(artifact, whitelist):
    return any([artifact.endswith(x) for x in whitelist])


def sanitize_en_US_binary(queue, task_id, gpg_key_path):
    # each platform en-US gets its own tempdir workground
    tempdir = tempfile.mkdtemp()
    log.debug('Temporary playground is %s', tempdir)

    # get all artifacts and trim but 'name' field from the json entries
    all_artifacts = [k['name'] for k in queue.listLatestArtifacts(task_id)['artifacts']]
    # filter files to hold the whitelist-related only
    artifacts = filter(lambda k: file_in_whitelist(k, ALL_FILES), all_artifacts)
    # filter out everything but the checkums artifacts
    checksums_artifacts = filter(lambda k: file_in_whitelist(k, CHECKSUMS), all_artifacts)
    other_artifacts = list(set(artifacts) - set(checksums_artifacts))
    # iterate in artifacts and grab checksums and its signature only
    log.info("Retrieve the checksums file and its signature ...")
    for artifact in checksums_artifacts:
        name = os.path.basename(artifact)
        build_url = queue.buildSignedUrl(
            'getLatestArtifact',
            task_id,
            artifact
        )
        log.debug('Downloading %s', name)
        try:
            r = requests.get(build_url, timeout=60)
            r.raise_for_status()
        except requests.HTTPError:
            log.exception("Failed to download %s file", name)
            raise SanityException("Failed to download %s file" % name)
        filepath = os.path.join(tempdir, name)
        with open(filepath, 'wb') as fd:
            for chunk in r.iter_content(1024):
                fd.write(chunk)
        if name.endswith(".checksums.asc"):
            signature = filepath
        else:
            checksums = filepath

    # perform the signatures validation test
    log.info("Attempt to validate signatures ...")
    validate_signatures(checksums, signature, tempdir, gpg_key_path)
    log.info("Signatures validated correctly!")

    log.info("Download all artifacts ...")
    download_all_artifacts(queue, other_artifacts, task_id, tempdir)
    log.info("All downloads completed!")

    log.info("Retrieve all sha512 from checksums file...")
    sha512_dict = parse_sha512(checksums, ALL_FILES - CHECKSUMS)
    log.info("All sha512 digests retrieved")

    log.info("Validating checksums for each artifact ...")
    validate_checksums(sha512_dict, tempdir)
    log.info("All checksums validated!")

    # remove entire playground before moving forward
    log.debug("Deleting the temporary playground ...")
    shutil.rmtree(tempdir)


def get_hash(path, hash_type="sha512"):
    h = hashlib.new(hash_type)
    with open(path, "rb") as f:
        for chunk in iter(functools.partial(f.read, 4096), ''):
            h.update(chunk)
    return h.hexdigest()


def validate_graph_kwargs(queue, gpg_key_path, **kwargs):
    validate_version(repo_path=kwargs["repo_path"],
                     revision=kwargs["revision"], version=kwargs["version"])
    # TODO: validate partials
    # TODO: validate l10n changesets
    platforms = kwargs.get('en_US_config', {}).get('platforms', {})
    for platform in platforms.keys():
        task_id = platforms.get(platform).get('task_id', {})
        log.info('Performing release sanity for %s en-US binary', platform)
        sanitize_en_US_binary(queue, task_id, gpg_key_path)

    log.info("Release sanity for all en-US is now completed!")


def main(options):
    log.info('Loading config from %s' % options.config)
    config = load_config(options.config)

    if config.getboolean('release-runner', 'verbose'):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",
                        level=log_level)
    # Suppress logging of retry(), see bug 925321 for the details
    logging.getLogger("util.retry").setLevel(logging.WARN)

    # Shorthand
    api_root = config.get('api', 'api_root')
    username = config.get('api', 'username')
    password = config.get('api', 'password')
    buildbot_configs = config.get('release-runner', 'buildbot_configs')
    buildbot_configs_branch = config.get('release-runner',
                                         'buildbot_configs_branch')
    sleeptime = config.getint('release-runner', 'sleeptime')
    notify_from = get_config(config, 'release-runner', 'notify_from', None)
    notify_to = get_config(config, 'release-runner', 'notify_to', None)
    docker_worker_key = get_config(config, 'release-runner',
                                   'docker_worker_key', None)
    signing_pvt_key = get_config(config, 'signing', 'pvt_key', None)
    if isinstance(notify_to, basestring):
        notify_to = [x.strip() for x in notify_to.split(',')]
    smtp_server = get_config(config, 'release-runner', 'smtp_server',
                             'localhost')
    tc_config = {
        "credentials": {
            "clientId": get_config(config, "taskcluster", "client_id", None),
            "accessToken": get_config(config, "taskcluster", "access_token", None),
        }
    }
    configs_workdir = 'buildbot-configs'
    balrog_username = get_config(config, "balrog", "username", None)
    balrog_password = get_config(config, "balrog", "password", None)
    extra_balrog_submitter_params = get_config(config, "balrog", "extra_balrog_submitter_params", None)
    beetmover_aws_access_key_id = get_config(config, "beetmover", "aws_access_key_id", None)
    beetmover_aws_secret_access_key = get_config(config, "beetmover", "aws_secret_access_key", None)
    gpg_key_path = get_config(config, "signing", "gpg_key_path", None)

    # TODO: replace release sanity with direct checks of en-US and l10n revisions (and other things if needed)

    rr = ReleaseRunner(api_root=api_root, username=username, password=password)
    scheduler = Scheduler(tc_config)
    index = Index(tc_config)
    queue = Queue(tc_config)

    # Main loop waits for new releases, processes them and exits.
    while True:
        try:
            log.debug('Fetching release requests')
            rr.get_release_requests()
            if rr.new_releases:
                for release in rr.new_releases:
                    log.info('Got a new release request: %s' % release)
                break
            else:
                log.debug('Sleeping for %d seconds before polling again' %
                          sleeptime)
                time.sleep(sleeptime)
        except:
            log.error("Caught exception when polling:", exc_info=True)
            sys.exit(5)

    retry(mercurial, args=(buildbot_configs, configs_workdir), kwargs=dict(branch=buildbot_configs_branch))

    if 'symlinks' in config.sections():
        format_dict = dict(buildbot_configs=configs_workdir)
        for target in config.options('symlinks'):
            symlink = config.get('symlinks', target).format(**format_dict)
            if path.exists(symlink):
                log.warning("Skipping %s -> %s symlink" % (symlink, target))
            else:
                log.info("Adding %s -> %s symlink" % (symlink, target))
                os.symlink(target, symlink)

    # TODO: this won't work for Thunderbird...do we care?
    branch = release["branch"].split("/")[-1]
    branchConfig = readBranchConfig(path.join(configs_workdir, "mozilla"), branch=branch)

    release_channels = update_channels(release["version"], branchConfig["release_channel_mappings"])
    # candidate releases are split in two graphs and release-runner only handles the first
    # graph of tasks. so parts like postrelease, push_to_releases/mirrors, and mirror dependant
    # channels are handled in the second generated graph outside of release-runner.
    # This is not elegant but it should do the job for now
    candidate_release = is_candidate_release(release_channels)
    if candidate_release:
        postrelease_enabled = False
        final_verify_channels = [
            c for c in release_channels if c not in branchConfig.get('mirror_requiring_channels', [])
        ]
        # TODO - use publish_to_balrog_channels once releasetasks publishes to balrog
        publish_to_balrog_channels = [
            c for c in release_channels if c not in branchConfig.get('mirror_requiring_channels', [])
        ]
        push_to_releases_enabled = False
    else:
        postrelease_enabled = branchConfig['postrelease_version_bump_enabled']
        final_verify_channels = release_channels
        publish_to_balrog_channels = release_channels
        push_to_releases_enabled = True

    rc = 0
    for release in rr.new_releases:
        graph_id = slugId()
        try:
            rr.update_status(release, 'Generating task graph')
            l10n_changesets = parsePlainL10nChangesets(rr.get_release_l10n(release["name"]))

            kwargs = {
                "public_key": docker_worker_key,
                "version": release["version"],
                "next_version": bump_version(release["version"]),
                "appVersion": getAppVersion(release["version"]),
                "buildNumber": release["buildNumber"],
                "source_enabled": True,
                "checksums_enabled": True,
                "repo_path": release["branch"],
                "revision": release["mozillaRevision"],
                "product": release["product"],
                # if mozharness_revision is not passed, use 'revision'
                "mozharness_changeset": release.get('mh_changeset') or release['mozillaRevision'],
                "partial_updates": getPartials(release),
                "branch": branch,
                "updates_enabled": bool(release["partials"]),
                "l10n_config": get_l10n_config(release, branchConfig, branch, l10n_changesets, index),
                "en_US_config": get_en_US_config(release, branchConfig, branch, index),
                "verifyConfigs": {},
                "balrog_api_root": branchConfig["balrog_api_root"],
                "funsize_balrog_api_root": branchConfig["funsize_balrog_api_root"],
                "balrog_username": balrog_username,
                "balrog_password": balrog_password,
                "beetmover_aws_access_key_id": beetmover_aws_access_key_id,
                "beetmover_aws_secret_access_key": beetmover_aws_secret_access_key,
                # TODO: stagin specific, make them configurable
                "signing_class": "release-signing",
                "bouncer_enabled": branchConfig["bouncer_enabled"],
                "release_channels": release_channels,
                "final_verify_channels": final_verify_channels,
                "signing_pvt_key": signing_pvt_key,
                "build_tools_repo_path": branchConfig['build_tools_repo_path'],
                "push_to_candidates_enabled": branchConfig['push_to_candidates_enabled'],
                "postrelease_bouncer_aliases_enabled": branchConfig['postrelease_bouncer_aliases_enabled'],
                "tuxedo_server_url": branchConfig['tuxedoServerUrl'],
                "postrelease_version_bump_enabled": postrelease_enabled,
                "push_to_releases_enabled": push_to_releases_enabled,
                "push_to_releases_automatic": branchConfig['push_to_releases_automatic'],
                "beetmover_candidates_bucket": branchConfig["beetmover_buckets"][release["product"]],
                "partner_repacks_platforms": branchConfig.get("partner_repacks_platforms", []),
                "l10n_changesets": l10n_changesets,
            }
            if extra_balrog_submitter_params:
                kwargs["extra_balrog_submitter_params"] = extra_balrog_submitter_params

            validate_graph_kwargs(queue, gpg_key_path, **kwargs)
            graph = make_task_graph(**kwargs)
            rr.update_status(release, "Submitting task graph")
            log.info("Task graph generated!")
            import pprint
            log.debug(pprint.pformat(graph, indent=4, width=160))
            print scheduler.createTaskGraph(graph_id, graph)

            rr.mark_as_completed(release)
            email_release_drivers(smtp_server=smtp_server, from_=notify_from,
                                  to=notify_to, release=release,
                                  graph_id=graph_id)
        except:
            # We explicitly do not raise an error here because there's no
            # reason not to start other releases if creating the Task Graph
            # fails for another one. We _do_ need to set this in order to exit
            # with the right code, though.
            rc = 2
            rr.mark_as_failed(
                release,
                'Failed to start release promotion (graph ID: %s)' % graph_id)
            log.exception("Failed to start release promotion for graph %s %s",
                          graph_id, release)

    if rc != 0:
        sys.exit(rc)

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
