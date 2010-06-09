# buildbot -> bouncer platform mapping
bouncer_platform_map = {'win32': 'win', 'macosx': 'osx', 'linux': 'linux'}
# buildbot -> ftp platform mapping
ftp_platform_map = {'win32': 'win32', 'macosx': 'mac', 'linux': 'linux-i686'}
# buildbot -> shipped-locales platform mapping
sl_platform_map = {'win32': 'win32', 'macosx': 'osx', 'linux': 'linux'}

def buildbot2bouncer(platform):
    return bouncer_platform_map.get(platform, platform)

def buildbot2ftp(platform):
    return ftp_platform_map.get(platform, platform)

def buildbot2shippedlocales(platform):
    return sl_platform_map.get(platform, platform)

def shippedlocales2buildbot(platform):
    try:
        return [k for k, v in sl_platform_map.iteritems() if v == platform][0]
    except IndexError:
        return platform

def getPlatformLocales(shipped_locales, platforms):
    platform_locales = {}
    for platform in platforms:
        platform_locales[platform] = []
    f = open(shipped_locales)
    for line in open(shipped_locales).readlines():
        entry = line.split()
        locale = entry[0]
        if len(entry)>1:
            for platform in entry[1:]:
                if shippedlocales2buildbot(platform) in platforms:
                    platform_locales[shippedlocales2buildbot(platform)].append(locale)
        else:
            for platform in platforms:
                platform_locales[platform].append(locale)
    f.close()
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
