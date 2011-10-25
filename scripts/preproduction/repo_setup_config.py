repoSetupConfig = {}
repoSetupConfig['hgHost'] = 'hg.mozilla.org'
repoSetupConfig['repoPath'] = 'users/prepr-ffxbld'
repoSetupConfig['hgUserName'] = 'prepr-ffxbld'
repoSetupConfig['hgSshKey'] = 'ffxbld_dsa'

repoSetupConfig['reposToClone'] = {
    'build/buildbot-configs': {
        'overrides': {
            'mozilla/release-firefox-mozilla-1.9.2.py': [
                'mozilla/preproduction_release_overrides.py',
                'mozilla/preproduction_release_overrides-1.9.2.py',
             ],
            'mozilla/release-firefox-mozilla-beta.py': [
                'mozilla/preproduction_release_overrides.py',
                'mozilla/preproduction_release_overrides-beta.py',
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
