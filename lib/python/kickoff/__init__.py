import re
import requests
import logging

from kickoff.api import Releases, Release, ReleaseL10n
from release.l10n import parsePlainL10nChangesets
from release.versions import getAppVersion
from util.sendmail import sendmail
from util.retry import retry

log = logging.getLogger(__name__)

# temporary regex to filter out anything but mozilla-beta and mozilla-release
# within release promotion. Once migration to release promotion is completed
# for all types of releases, we will backout this filtering
# regex beta tracking bug is 1252333,
# regex release tracking bug is 1263976
RELEASE_PATTERNS = [
    r"Firefox-.*"
]


def matches(name, patterns):
    return any([re.search(p, name) for p in patterns])


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

def email_release_drivers(smtp_server, from_, to, release, task_group_id):
    # Send an email to the mailing after the build

    content = """\
A new build has been submitted through ship-it:

Commit: https://hg.mozilla.org/{path}/rev/{revision}
Task group: https://tools.taskcluster.net/push-inspector/#/{task_group_id}/

Created by {submitter}
Started by {starter}


""".format(path=release["branch"], revision=release["mozillaRevision"],
           submitter=release["submitter"], starter=release["starter"],
           task_group_id=task_group_id)

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


def get_partials(rr, partial_versions, product):
    partials = {}
    if not partial_versions:
        return partials
    for p in [stripped.strip() for stripped in partial_versions.split(',')]:
        partialVersion, buildNumber = p.split('build')
        partial_release_name = '{}-{}-build{}'.format(
            product.capitalize(), partialVersion, buildNumber,
        )
        partials[partialVersion] = {
            'appVersion': getAppVersion(partialVersion),
            'buildNumber': buildNumber,
            'locales': parsePlainL10nChangesets(
                rr.get_release_l10n(partial_release_name)).keys(),
        }
    return partials


def get_platform_locales(l10n_changesets, platform):
    # hardcode ja/ja-JP-mac exceptions
    if platform == "macosx64":
        ignore = "ja"
    else:
        ignore = "ja-JP-mac"

    return [l for l in l10n_changesets.keys() if l != ignore]


def task_for_revision(index, branch, revision, product, platform):
    return index.findTask(
        "gecko.v2.{branch}.revision.{rev}.{product}.{platform}-opt".format(
        rev=revision, branch=branch, product=product, platform=platform))


def get_l10n_config(index, product, branch, revision, platforms,
                    l10n_platforms, l10n_changesets):
    l10n_platform_configs = {}
    for platform in l10n_platforms:
        task = task_for_revision(index, branch, revision, product, platform)
        url = "https://queue.taskcluster.net/v1/task/{taskid}/artifacts/public/build".format(
            taskid=task["taskId"]
        )
        l10n_platform_configs[platform] = {
            "locales": get_platform_locales(l10n_changesets, platform),
            "en_us_binary_url": url,
            "chunks": platforms[platform].get("l10n_chunks", 10),
        }

    return {
        "platforms": l10n_platform_configs,
        "changesets": l10n_changesets,
    }


def get_en_US_config(index, product, branch, revision, platforms):
    platform_configs = {}
    for platform in platforms:
        task = task_for_revision(index, branch, revision, product, platform)
        platform_configs[platform] = {
            "task_id": task["taskId"]
        }

    return {
        "platforms": platform_configs,
    }


# FIXME: the following function should be removed and we should use
# next_version provided by ship-it
def bump_version(version):
    """Bump last digit

    >>> bump_version("45.0")
    '45.0.1'
    >>> bump_version("45.0.1")
    '45.0.2'
    >>> bump_version("45.0b3")
    '45.0b4'
    >>> bump_version("45.0esr")
    '45.0.1esr'
    >>> bump_version("45.0.1esr")
    '45.0.2esr'
    >>> bump_version("45.2.1esr")
    '45.2.2esr'
    """
    split_by = "."
    digit_index = 2
    suffix = ""
    if "b" in version:
        split_by = "b"
        digit_index = 1
    if "esr" in version:
        version = version.replace("esr", "")
        suffix = "esr"
    v = version.split(split_by)
    if len(v) < digit_index + 1:
        # 45.0 is 45.0.0 actually
        v.append("0")
    v[-1] = str(int(v[-1]) + 1)
    return split_by.join(v) + suffix


def make_task_graph_strict_kwargs(appVersion, balrog_api_root, balrog_password, balrog_username,
                                  beetmover_aws_access_key_id, beetmover_aws_secret_access_key,
                                  beetmover_candidates_bucket, bouncer_enabled, branch, buildNumber,
                                  build_tools_repo_path, checksums_enabled, en_US_config,
                                  extra_balrog_submitter_params, final_verify_channels,
                                  final_verify_platforms, uptake_monitoring_platforms,
                                  funsize_balrog_api_root, l10n_config,
                                  l10n_changesets, mozharness_changeset, next_version,
                                  partial_updates, partner_repacks_platforms,
                                  postrelease_bouncer_aliases_enabled, uptake_monitoring_enabled,
                                  postrelease_version_bump_enabled,
                                  postrelease_mark_as_shipped_enabled,
                                  product, public_key, push_to_candidates_enabled,
                                  push_to_releases_automatic, push_to_releases_enabled, release_channels,
                                  repo_path, revision, signing_class, signing_pvt_key, source_enabled,
                                  tuxedo_server_url, update_verify_enabled, updates_builder_enabled,
                                  updates_enabled, verifyConfigs, version, publish_to_balrog_channels):
    """simple wrapper that sanitizes whatever calls make_task_graph uses universally known kwargs"""

    kwargs = dict(
        appVersion=appVersion,
        balrog_api_root=balrog_api_root,
        balrog_password=balrog_password,
        balrog_username=balrog_username,
        beetmover_aws_access_key_id=beetmover_aws_access_key_id,
        beetmover_aws_secret_access_key=beetmover_aws_secret_access_key,
        beetmover_candidates_bucket=beetmover_candidates_bucket,
        bouncer_enabled=bouncer_enabled,
        branch=branch,
        buildNumber=buildNumber,
        build_tools_repo_path=build_tools_repo_path,
        checksums_enabled=checksums_enabled,
        en_US_config=en_US_config,
        final_verify_channels=final_verify_channels,
        final_verify_platforms=final_verify_platforms,
        uptake_monitoring_platforms=uptake_monitoring_platforms,
        funsize_balrog_api_root=funsize_balrog_api_root,
        l10n_changesets=l10n_changesets,
        l10n_config=l10n_config,
        mozharness_changeset=mozharness_changeset,
        next_version=next_version,
        partial_updates=partial_updates,
        partner_repacks_platforms=partner_repacks_platforms,
        postrelease_bouncer_aliases_enabled=postrelease_bouncer_aliases_enabled,
        uptake_monitoring_enabled=uptake_monitoring_enabled,
        postrelease_version_bump_enabled=postrelease_version_bump_enabled,
        postrelease_mark_as_shipped_enabled=postrelease_mark_as_shipped_enabled,
        product=product,
        public_key=public_key,
        push_to_candidates_enabled=push_to_candidates_enabled,
        push_to_releases_automatic=push_to_releases_automatic,
        push_to_releases_enabled=push_to_releases_enabled,
        release_channels=release_channels,
        repo_path=repo_path,
        revision=revision,
        signing_class=signing_class,
        signing_pvt_key=signing_pvt_key,
        source_enabled=source_enabled,
        tuxedo_server_url=tuxedo_server_url,
        update_verify_enabled=update_verify_enabled,
        updates_builder_enabled=updates_builder_enabled,
        updates_enabled=updates_enabled,
        verifyConfigs=verifyConfigs,
        version=version,
        publish_to_balrog_channels=publish_to_balrog_channels,
    )
    if extra_balrog_submitter_params:
        kwargs["extra_balrog_submitter_params"] = extra_balrog_submitter_params

    # don't import releasetasks until required within function impl to avoid global failures
    # during nosetests
    from releasetasks import make_task_graph
    return make_task_graph(**kwargs)
