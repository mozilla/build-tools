from datetime import datetime
import os
from os import path
import shutil
import sys
from time import strftime
from urllib2 import urlopen

from release.paths import makeCandidatesDir

import logging
log = logging.getLogger(__name__)

class ConfigError(Exception):
    pass

def getBuildID(platform, product, version, buildNumber, nightlyDir='nightly',
               server='stage.mozilla.org', verbose=False):
    infoTxt = makeCandidatesDir(product, version, buildNumber, nightlyDir,
                                protocol='http', server=server) + \
              '%s_info.txt' % platform
    try:
        buildInfo = urlopen(infoTxt).read()
    except:
        if verbose:
            print >>sys.stderr, "Failed to retrieve %s" % infoTxt
        raise

    for line in buildInfo.splitlines():
        key,value = line.rstrip().split('=', 1)
        if key == 'buildID':
            return value

def findOldBuildIDs(product, version, buildNumber, platforms,
                    nightlyDir='nightly', server='stage.mozilla.org',
                    verbose=False):
    ids = {}
    if buildNumber <= 1:
        return ids
    for n in range(1, buildNumber):
        for platform in platforms:
            if platform not in ids:
                ids[platform] = []
            try:
                id = getBuildID(platform, product, version, n, nightlyDir,
                                server, verbose)
                ids[platform].append(id)
            except Exception, e:
                if verbose:
                    print >>sys.stderr, "Hit exception: %s" % e
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

def getTags(baseTag, buildNumber, buildTag=True):
    t = ['%s_RELEASE' % baseTag]
    if buildTag:
        t.append('%s_BUILD%d' % (baseTag, int(buildNumber)))
    return t

def generateRelbranchName(milestone, prefix='GECKO'):
    return '%s%s_%s_RELBRANCH' % (
      prefix, milestone.replace('.', ''),
      datetime.now().strftime('%Y%m%d'))
