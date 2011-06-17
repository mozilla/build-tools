from urllib2 import urlopen
from urlparse import urljoin

from build.l10n import getLocalesForChunk
from release.platforms import buildbot2ftp, getPlatformLocales, \
                              getPlatformLocalesFromJson
from release.versions import getPrettyVersion

import logging
log = logging.getLogger(__name__)

def getShippedLocales(product, appName, version, buildNumber, sourceRepo,
                      hg='http://hg.mozilla.org'):
    tag = '%s_%s_BUILD%s' % (product.upper(), version.replace('.', '_'),
                             str(buildNumber))
    file = '%s/raw-file/%s/%s/locales/shipped-locales' % \
      (sourceRepo, tag, appName)
    url = urljoin(hg, file)
    try:
        sl = urlopen(url).read()
    except:
        log.error("Failed to retrieve %s", url)
        raise
    return sl

def getCommonLocales(a, b):
    return [locale for locale in a if locale in b]

def getL10nRepositories(file, l10nRepoPath, relbranch=None):
    """Reads in a list of locale names and revisions for their associated
       repository from 'file'.
    """
    # urljoin() will strip the last part of l10nRepoPath it doesn't end with "/"
    if not l10nRepoPath.endswith('/'):
        l10nRepoPath = l10nRepoPath + '/'
    repositories = {}
    for localeLine in open(file).readlines():
        locale, revision = localeLine.rstrip().split()
        if revision == 'FIXME':
            raise Exception('Found FIXME in %s for locale "%s"' % \
                           (file, locale))
        locale = urljoin(l10nRepoPath, locale)
        repositories[locale] = {
            'revision': revision,
            'relbranchOverride': relbranch,
            'bumpFiles': []
        }

    return repositories


def makeReleaseRepackUrls(productName, brandName, version, appVersion,
                          platform, locale='en-US'):
    longVersion = version
    builds = {}
    if productName not in ('fennec',):
        platformDir = buildbot2ftp(platform)
        if platform.startswith('linux'):
            filename = '%s.tar.bz2' % productName
            builds[filename] = '/'.join([p.strip('/') for p in [
                platformDir, locale, '%s-%s.tar.bz2' % (productName, version)]])
        elif platform.startswith('macosx'):
            filename = '%s.dmg' % productName
            builds[filename] = '/'.join([p.strip('/') for p in [
                platformDir, locale, '%s %s.dmg' % (brandName, longVersion)]])
        elif platform.startswith('win'):
            filename = '%s.zip' % productName
            instname = '%s.exe' % productName
            builds[filename] = '/'.join([p.strip('/') for p in [
                'unsigned', platformDir, locale,
                '%s-%s.zip' % (productName, version)]])
            builds[instname] = '/'.join([p.strip('/') for p in [
                'unsigned', platformDir, locale,
                '%s Setup %s.exe' % (brandName, longVersion)]])
        else:
            raise "Unsupported platform"
    else:
        if platform == 'linux':
            filename = '%s.tar.bz2' % productName
            builds[filename] = '/'.join([p.strip('/') for p in [
                platform, locale, '%s-%s.%s.linux-i686.tar.bz2' % (productName, appVersion, locale)]])
        elif platform == 'macosx':
            filename = '%s.dmg' % productName
            builds[filename] = '/'.join([p.strip('/') for p in [
                platform, locale, '%s-%s.%s.mac.dmg' % (brandName, appVersion, locale)]])
        elif platform == 'win32':
            filename = '%s.zip' % productName
            builds[filename] = '/'.join([p.strip('/') for p in [
                platform, locale,
                '%s-%s.%s.win32.zip' % (productName, appVersion, locale)]])
        else:
            raise "Unsupported platform"
    
    return builds

def getReleaseLocalesForChunk(productName, appName, version, buildNumber,
                              sourceRepo, platform, chunks, thisChunk,
                              hg='http://hg.mozilla.org'):
    possibleLocales = getPlatformLocales(
        getShippedLocales(productName, appName, version, buildNumber,
                          sourceRepo, hg),
        (platform,)
    )[platform]
    return getLocalesForChunk(possibleLocales, chunks, thisChunk)

def getReleaseLocalesFromJsonForChunk(stage_platform, chunks, thisChunk, jsonFile):
    possibleLocales = getPlatformLocalesFromJson(jsonFile, (stage_platform,))[stage_platform]
    return getLocalesForChunk(possibleLocales, chunks, thisChunk)
