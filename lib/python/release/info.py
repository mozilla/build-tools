from datetime import datetime
import os
from os import path
import re
import shutil
import sys
from urllib2 import urlopen

from release.paths import makeCandidatesDir

import logging
log = logging.getLogger(__name__)

# If version has two parts with no trailing specifiers like "rc", we
# consider it a "final" release for which we only create a _RELEASE tag.
FINAL_RELEASE_REGEX = "^\d+\.\d+$"

class ConfigError(Exception):
    pass

def getBuildID(platform, product, version, buildNumber, nightlyDir='nightly',
               server='stage.mozilla.org'):
    infoTxt = makeCandidatesDir(product, version, buildNumber, nightlyDir,
                                protocol='http', server=server) + \
              '%s_info.txt' % platform
    try:
        buildInfo = urlopen(infoTxt).read()
    except:
        log.error("Failed to retrieve %s" % infoTxt)
        raise

    for line in buildInfo.splitlines():
        key,value = line.rstrip().split('=', 1)
        if key == 'buildID':
            return value

def findOldBuildIDs(product, version, buildNumber, platforms,
                    nightlyDir='nightly', server='stage.mozilla.org'):
    ids = {}
    if buildNumber <= 1:
        return ids
    for n in range(1, buildNumber):
        for platform in platforms:
            if platform not in ids:
                ids[platform] = []
            try:
                id = getBuildID(platform, product, version, n, nightlyDir,
                                server)
                ids[platform].append(id)
            except Exception, e:
                log.error("Hit exception: %s" % e)
    return ids

def readReleaseConfig(configfile, required=[]):
    return readConfig(configfile, keys=['releaseConfig'], required=required)

def readBranchConfig(dir, localconfig, branch, required=[]):
    shutil.copy(localconfig, path.join(dir, "localconfig.py"))
    oldcwd = os.getcwd()
    os.chdir(dir)
    sys.path.append(".")
    try:
        return readConfig("config.py", keys=['BRANCHES', branch],
                          required=required)
    finally:
        os.chdir(oldcwd)
        sys.path.remove(".")

def readConfig(configfile, keys=[], required=[]):
    c = {}
    execfile(configfile, c)
    for k in keys:
        c = c[k]
    items = c.keys()
    err = False
    for key in required:
        if key not in items:
            err = True
            log.error("Required item `%s' missing from %s" % (key, c))
    if err:
        raise ConfigError("Missing at least one item in config, see above")
    return c

def isFinalRelease(version):
    return bool(re.match(FINAL_RELEASE_REGEX, version))

def getTags(baseTag, buildNumber, buildTag=True):
    t = ['%s_RELEASE' % baseTag]
    if buildTag:
        t.append('%s_BUILD%d' % (baseTag, int(buildNumber)))
    return t

def getRuntimeTag(tag):
    return "%s_RUNTIME" % tag

def generateRelbranchName(milestone, prefix='GECKO'):
    return '%s%s_%s_RELBRANCH' % (
      prefix, milestone.replace('.', ''),
      datetime.now().strftime('%Y%m%d%H'))

def getRepoMatchingBranch(branch, sourceRepositories):
    for sr in sourceRepositories.values():
        if branch in sr['path']:
            return sr
    return None

