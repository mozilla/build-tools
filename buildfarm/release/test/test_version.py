import unittest
import requests
from release.test import get_display_version, make_repo_request


class TestRevision(unittest.TestCase):
    kwargs = None

    def setUp(self):
        from l10n import l10n_changesets
        self.kwargs = {
                "public_key": None,
                "version": "46.0b4",
                "next_version": "46.0b5",
                "appVersion": "46.0",
                "buildNumber": 3,
                "source_enabled": True,
                "checksums_enabled": True,
                "repo_path": "releases/mozilla-beta",
                "revision": "2f6f69a19150e03ad68062f2ac92342afb1ef787",
                "product": "firefox",
                "mozharness_changeset": "2f6f69a19150e03ad68062f2ac92342afb1ef787",
                "partial_updates": {
                    "38.0": {
                        "buildNumber": 1,
                        "locales": ["de", "en-GB", "zh-TW"],
                    },
                    "37.0": {
                        "buildNumber": 2,
                        "locales": ["de", "en-GB", "zh-TW"],
                    },
                },
                "branch": "mozilla-beta",
                "updates_enabled": False,
                # TODO:
                "l10n_config": {},
                "en_US_config": {
                    "platforms": {
                        "macosx64": {"task_id": "abc"},
                        "win32": {"task_id": "def"},
                        "win64": {"task_id": "jgh"},
                        "linux": {"task_id": "ijk"},
                        "linux64": {"task_id": "lmn"},
                    }
                },
                "verifyConfigs": {},
                "balrog_api_root": "https://balrog.real/api",
                "funsize_balrog_api_root": "http://balrog/api",
                "balrog_username": 'username',
                "balrog_password": 'password',
                "beetmover_aws_access_key_id": None,
                "beetmover_aws_secret_access_key": None,
                "signing_class": "release-signing",
                "bouncer_enabled": True,
                "updates_builder_enabled": False,
                "update_verify_enabled": False,
                "release_channels": ["foo"],
                "final_verify_channels": ["release"],
                "final_verify_platforms": ["macosx64", "win32", "win64", "linux", "linux64"],
                "uptake_monitoring_platforms": ["macosx64", "win32", "win64", "linux", "linux64"],
                "signing_pvt_key": None,
                "build_tools_repo_path": "build/tools",
                "push_to_candidates_enabled": True,
                "postrelease_bouncer_aliases_enabled": False,
                "uptake_monitoring_enabled": True,
                "tuxedo_server_url": "https://bouncer.real.allizom.org/api",
                "postrelease_version_bump_enabled": False,
                "push_to_releases_enabled": True,
                "push_to_releases_automatic": False,
                "beetmover_candidates_bucket": 'mozilla-releng-beet-mover-dev',
                "partner_repacks_platforms": ["macosx64", "win32", "win64", "linux", "linux64"],
                "l10n_changesets": l10n_changesets,
                "extra_balrog_submitter_params": None,
                "publish_to_balrog_channels": None,
        }

    def test_validate_branch_and_revision_in_tree(self):
        repo_path = self.kwargs["repo_path"]
        revision = self.kwargs["revision"]

        try:
            make_repo_request(repo_path, revision)
        except requests.HTTPError:
            # TODO: add logging overall + here
            err_msg = "Repo does not exist with required revision."
            self.fail(err_msg)

    def test_validate_version_in_tree(self):
        repo_path = self.kwargs["repo_path"]
        revision = self.kwargs["revision"]
        version = self.kwargs["version"].replace("esr", "")

        actual_version = get_display_version(repo_path, revision)
        msg = "In-tree version '{tree_version}' doesn't match ship-it version '{version}'"
        self.assertEqual(version, actual_version, msg.format(version=version, tree_version=actual_version))
