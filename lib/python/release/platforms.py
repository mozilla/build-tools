# buildbot -> bouncer platform mapping
# TODO: make sure 'win64' is correct when Bouncer becomes aware of
# 64-bit windows
try:
    import simplejson as json
except:
    import json
bouncer_platform_map = {'win32': 'win', 'win64': 'win64', 'macosx': 'osx',
                        'linux': 'linux', 'linux64': 'linux64',
                        'macosx64': 'osx', 'win32-EUballot': 'win'}
# buildbot -> ftp platform mapping
ftp_platform_map = {'win32': 'win32', 'win64': 'win64', 'macosx': 'mac',
                    'linux': 'linux-i686', 'linux64': 'linux-x86_64',
                    'macosx64': 'mac', 'linux-android': 'android',
                    'linux-mobile': 'linux', 'macosx-mobile': 'macosx',
                    'win32-mobile': 'win32', 'android': 'android',
                    'android-xul': 'android-xul'}
# buildbot -> shipped-locales platform mapping
# TODO: make sure 'win64' is correct when shipped-locales becomes aware of it
sl_platform_map = {'win32': 'win32', 'win64': 'win64', 'macosx': 'osx',
                   'linux': 'linux', 'linux64': 'linux', 'macosx64': 'osx'}
# buildbot -> update platform mapping
update_platform_map = {
    'linux': ['Linux_x86-gcc3'],
    'linux64': ['Linux_x86_64-gcc3'],
    'macosx': ['Darwin_Universal-gcc3', 'Darwin_x86-gcc3-u-ppc-i386',
               'Darwin_ppc-gcc3-u-ppc-i386'],
    'macosx64': ['Darwin_x86_64-gcc3', 'Darwin_x86-gcc3-u-i386-x86_64',
                 'Darwin_x86_64-gcc3-u-i386-x86_64'],
    'win32': ['WINNT_x86-msvc'],
    'win64': ['WINNT_x86_64-msvc'],
}

def buildbot2bouncer(platform):
    return bouncer_platform_map.get(platform, platform)

def buildbot2ftp(platform):
    return ftp_platform_map.get(platform, platform)

def buildbot2shippedlocales(platform):
    return sl_platform_map.get(platform, platform)

def shippedlocales2buildbot(platform):
    matches = []
    try:
        [matches.append(k) for k, v in sl_platform_map.iteritems() if v == platform][0]
        return matches
    except IndexError:
        return [platform]

def buildbot2updatePlatforms(platform):
    return update_platform_map.get(platform, [platform])

def getPlatformLocales(shipped_locales, platforms):
    platform_locales = {}
    for platform in platforms:
        platform_locales[platform] = []
    for line in shipped_locales.splitlines():
        entry = line.strip().split()
        locale = entry[0]
        if len(entry)>1:
            for platform in entry[1:]:
                for bb_platform in shippedlocales2buildbot(platform):
                    if bb_platform in platforms:
                        platform_locales[bb_platform].append(locale)
        else:
            for platform in platforms:
                platform_locales[platform].append(locale)
    return platform_locales

def getLocaleListFromShippedLocales(shipped_locales):
    """ return the list of locales in shipped_locales, without platform specific info """
    shipped_locales_list = []
    for line in shipped_locales.splitlines():
        entry = line.strip().split()
        shipped_locales_list.append(entry[0])
    return shipped_locales_list

def getPlatformLocalesFromJson(json_file, platforms):
    platform_locales = {}
    for platform in platforms:
        platform_locales[platform] = []
    fh = open(json_file)
    json_contents = json.load(fh)
    fh.close()
    for locale in json_contents.keys():
        for platform in json_contents[locale]["platforms"]:
            if platform not in platform_locales:
                platform_locales[platform] = []
            platform_locales[platform].append(locale)
    return platform_locales

def getAllLocales(shipped_locales):
    locales = []
    f = open(shipped_locales)
    for line in f.readlines():
        entry = line.split()
        locale = entry[0]
        if locale:
            locales.append(locale)
    f.close()
    return locales

def getPlatforms():
    return bouncer_platform_map.keys()

def getSupportedPlatforms():
    return ('linux', 'linux64', 'win32', 'win64', 'macosx', 'macosx64')
