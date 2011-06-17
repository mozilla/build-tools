import os
from os import path
import urllib
from urllib import urlretrieve

from release.platforms import ftp_platform_map
from release.l10n import makeReleaseRepackUrls
from release.paths import makeCandidatesDir
from util.paths import windows2msys
from util.file import directoryContains

import logging
log = logging.getLogger(__name__)

installer_ext_map = {
    'win32' : ".exe",
    'win64' : ".exe",
    'macosx' : ".dmg",
    'macosx64' : ".dmg",
    'linux' : ".tar.bz2",
    'linux64' : ".tar.bz2",
}

def getInstallerExt(platform):
    """ Return the file extension of the installer file on a given platform,
    raising a KeyError if the platform is not found """
    return installer_ext_map[platform]

def downloadReleaseBuilds(stageServer, productName, brandName, version,
                          buildNumber, platform, appVersion=None,
                          candidatesDir=None):
    if appVersion is None:
        appVersion = version
    if candidatesDir is None:
        candidatesDir = makeCandidatesDir(productName, version, buildNumber,
                                          protocol='http', server=stageServer)
    files = makeReleaseRepackUrls(productName, brandName, version, appVersion,
                                  platform)

    env = {}
    for file,remoteFile in files.iteritems():
        url = '/'.join([p.strip('/') for p in [candidatesDir,
                                               urllib.quote(remoteFile)]])
        log.info("Downloading %s to %s", url, file)
        urlretrieve(url, file)
        if file.endswith('exe'):
            env['WIN32_INSTALLER_IN'] = windows2msys(path.join(os.getcwd(),
                                                     file))
        else:
            if platform.startswith('win'):
                env['ZIP_IN'] = windows2msys(path.join(os.getcwd(), file))
            else:
                env['ZIP_IN'] = path.join(os.getcwd(), file)

    return env

def expectedFiles(unsignedDir, locale, platform, signedPlatforms,
        firstLocale='en-US'):
    """ When checking a full set of downloaded release builds,
    for a given locale + platform check for the following:
    - container package file for a given locale + platform (i.e. exe, dmg)
    - an XPI pack
    - a complete MAR
    """
    unsigned = 'unsigned' if platform in signedPlatforms else ''
    expectedDir = os.path.join(unsignedDir, unsigned, ftp_platform_map[platform], locale)
    log.debug("looking for %s" % expectedDir)
    updatesDir = os.path.join(unsignedDir, unsigned, 'update', ftp_platform_map[platform], locale)
    langpackDir = os.path.join(unsignedDir, unsigned, ftp_platform_map[platform], 'xpi')

    if os.path.isdir(expectedDir):
        packages = directoryContains(expectedDir, installer_ext_map[platform])
    else:
        log.error("%s does not exist", expectedDir)
        packages = False

    if os.path.isdir(updatesDir):
        update = directoryContains(updatesDir, '.complete.mar')
    else:
        log.error("%s does not exist", updatesDir)
        update = False

    if os.path.isdir(langpackDir):
        langpack = directoryContains(langpackDir, "%s.xpi" % locale) or \
            locale == firstLocale
    else:
        log.error("%s does not exist", langpackDir)
        langpack = False

    return update and packages and langpack
