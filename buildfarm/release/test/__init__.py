import requests
import site
from os import path

site.addsitedir(path.join(path.dirname(__file__), "../../../lib/python"))
from util.retry import retry
from util.hg import make_hg_url


def make_head_request(url):
    """Make a HEAD request to check page existence"""
    def _get():
        req = requests.head(url, timeout=60)
        req.raise_for_status()

    return retry(_get, attempts=5, sleeptime=1)


def make_repo_request(repo_path,
                      revision):
    """Attempt to validate indicated repo path and revision"""
    url = make_hg_url('hg.mozilla.org', repo_path, revision=revision)

    return make_head_request(url)


def get_display_version(repo_path,
                        revision,
                        filename='browser/config/version_display.txt'):
    """Get display version from remote repository

    >>> get_display_version("releases/mozilla-beta", "59f372c35b24")
    '46.0b3'

    >>> get_display_version("releases/mozilla-beta", "59f372c35b2416ac84d6572d64c49227481a8a6c")
    '46.0b3'
    """
    # The location is the same for both Firefox and Fennec
    url = make_hg_url('hg.mozilla.org', repo_path,
                      revision=revision, filename=filename)

    def _get():
        req = requests.get(url, timeout=60)
        req.raise_for_status()
        return req.content.strip()

    return retry(_get)


def get_upstream_mh_config(repo_path, revision, filename):
    """TODO"""
    url = make_hg_url('hg.mozilla.org', repo_path,
                      revision=revision, filename=filename)

    def _get():
        req = requests.get(url, timeout=60)
        req.raise_for_status()
        return req.content.strip()

    return retry(_get)


def get_single_locale_config(repo_path,
                             revision,
                             branch,
                             filename='testing/mozharness/configs/single_locale/{branch}.py'):
    """Get single locale from remote mh configs
    Example for mozilla-beta, random revision:

    >>>
    config = {
        "nightly_build": True,
        "branch": "mozilla-beta",
        ...
        # l10n
        "hg_l10n_base": "https://hg.mozilla.org/releases/l10n/mozilla-beta",
        # repositories
        "mozilla_dir": "mozilla-beta",
        'purge_minsize': 12,
        'is_automation': True,
        ...
        'default_actions': [
            "clobber",
            "pull",
            "list-locales",
            "setup",
            "repack",
            "taskcluster-upload",
            "summary",
        ],
        ...
    }
    """
    assert branch
    filename = filename.format(branch=branch)

    return get_upstream_mh_config(repo_path, revision, filename)


def get_releases_bouncer_config(repo_path,
                                revision,
                                branch,
                                filename='testing/mozharness/configs/releases/bouncer_{ff_branch}.py'):
    """TODO"""
    assert branch
    _ = branch.replace("-", "_")
    filename = filename.format(ff_branch=_.replace("mozilla","firefox"))

    return get_upstream_mh_config(repo_path, revision, filename)
