import os
from os import path
import urllib
from urllib import urlretrieve

from release.l10n import makeReleaseRepackUrls
from release.paths import makeCandidatesDir
from util.paths import windows2msys

import logging
log = logging.getLogger(__name__)

def downloadReleaseBuilds(stageServer, productName, brandName, version,
                          buildNumber, platform):
    candidatesDir = makeCandidatesDir(productName, version, buildNumber,
                                      protocol='http', server=stageServer)
    files = makeReleaseRepackUrls(productName, brandName, version, platform)

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
