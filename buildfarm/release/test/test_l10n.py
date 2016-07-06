import unittest
import requests
from release.test import get_single_locale_config, make_head_request


class TestL10n(unittest.TestCase):
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
                "l10n_config": {
                        "platforms": {
                            "win32": {
                                "en_us_binary_url": "https://queue.taskcluster.net/something/firefox.exe",
                                "locales": ["de", "en-GB", "zh-TW"],
                                "chunks": 1,
                            },
                            "linux64": {
                                "en_us_binary_url": "https://queue.taskcluster.net/something/firefox.tar.xz",
                                "locales": ["de", "en-GB", "zh-TW"],
                                "chunks": 1,
                            },

                        },
                        "changesets": {
                            "de": "default",
                            "en-GB": "default",
                            "zh-TW": "default",
                        },
                },
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

        ret = get_single_locale_config(self.kwargs["repo_path"],
                                       self.kwargs["revision"],
                                       self.kwargs["branch"])
        exec ret
        single_locale_config = locals().get('config')
        self.kwargs.update(single_locale_config)

    def test_verify_l10n_changesets(self):
        locales = self.kwargs["l10n_changesets"]
        for locale in sorted(locales.keys()):
            revision = locales[locale]

            locale_url = "{hg_l10n_base}/{locale}/raw-file/{revision}".format(
                hg_l10n_base=self.kwargs["hg_l10n_base"].strip('/'),
                locale=locale,
                revision=revision
            )

            try:
                make_head_request(locale_url)
            except requests.HTTPError:
                # TODO: add logging overall + here
                err_msg = "{locale} locale with revision {revision} not found".format(
                    locale=locale,
                    revision=revision
                )
                self.fail(err_msg)
