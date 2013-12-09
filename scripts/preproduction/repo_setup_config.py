repoSetupConfig = {}
repoSetupConfig['hgHost'] = 'hg.mozilla.org'
repoSetupConfig['repoPath'] = 'users/prepr-ffxbld'
repoSetupConfig['hgUserName'] = 'prepr-ffxbld'
repoSetupConfig['hgSshKey'] = 'ffxbld_dsa'

repoSetupConfig['reposToClone'] = {
    'build/buildbot-configs': {
        'overrides': {
            'mozilla/release-firefox-mozilla-esr24.py': [
                'mozilla/preproduction_release_overrides.py',
                'mozilla/preproduction_release_overrides-esr24.py',
            ],
            'mozilla/release-firefox-mozilla-beta.py': [
                'mozilla/preproduction_release_overrides.py',
                'mozilla/preproduction_release_overrides-beta.py',
            ],
            'mozilla/release-firefox-mozilla-release.py': [
                'mozilla/preproduction_release_overrides.py',
                'mozilla/preproduction_release_overrides-release.py',
            ],
        },
        'nobump_overrides': {
            'mozilla/preproduction_config.py': [
                'mozilla/preproduction_config_overrides.py',
            ],
        },
        'doTag': True,
    },
    'build/tools': {
        'doTag': True,
    },
    'build/buildbotcustom': {},
    'build/buildbot': {},
    'build/compare-locales': {},
    'build/partner-repacks': {},
    'build/mozharness': {},
}
