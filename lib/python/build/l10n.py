import os
from os import path
import shutil
import sys
from urllib2 import urlopen
from urlparse import urljoin

from release.platforms import getPlatformLocales
from util.commands import run_cmd
from util.hg import mercurial, update
from util.paths import windows2msys
from util.retry import retry

import logging
log = logging.getLogger(__name__)

def getAllLocales(appName, sourceRepo, rev="default",
                  hg="http://hg.mozilla.org"):
    localeFile = "%s/raw-file/%s/%s/locales/all-locales" % \
      (sourceRepo, rev, appName)
    url = urljoin(hg, localeFile)
    try:
        sl = urlopen(url).read()
    except:
        log.error("Failed to retrieve %s", url)
        raise
    return sl

def compareLocales(repo, locale, l10nRepoDir, localeSrcDir, l10nIni,
                   revision="default", merge=True):
    retry(mercurial, args=(repo, "compare-locales"))
    update("compare-locales", revision=revision)
    mergeDir = path.join(localeSrcDir, "merged")
    if path.exists(mergeDir):
        log.info("Deleting %s" % mergeDir)
        shutil.rmtree(mergeDir)
    run_cmd(["python", path.join("compare-locales", "scripts",
                                 "compare-locales"),
             "-m", mergeDir,
             l10nIni,
             l10nRepoDir, locale],
             env={"PYTHONPATH": path.join("compare-locales", "lib")})

def l10nRepackPrep(sourceRepoName, objdir, mozconfigPath,
                   l10nBaseRepoName, makeDirs, localeSrcDir, env):
    if not path.exists(l10nBaseRepoName):
        os.mkdir(l10nBaseRepoName)
    shutil.copy(mozconfigPath, path.join(sourceRepoName, ".mozconfig"))
    run_cmd(["make", "-f", "client.mk", "configure"], cwd=sourceRepoName,
            env=env)
    for dir in makeDirs:
        run_cmd(["make"], cwd=path.join(sourceRepoName, objdir, dir), env=env)

def repackLocale(locale, l10nRepoDir, l10nBaseRepo, revision, localeSrcDir,
                 l10nIni, compareLocalesRepo, env, merge=True):
    repo = "/".join([l10nBaseRepo, locale])
    localeDir = path.join(l10nRepoDir, locale)
    retry(mercurial, args=(repo, localeDir))
    update(localeDir, revision=revision)
    
    compareLocales(compareLocalesRepo, locale, l10nRepoDir, localeSrcDir,
                   l10nIni, revision=revision, merge=merge)
    env["AB_CD"] = locale
    env["LOCALE_MERGEDIR"] = path.abspath(path.join(localeSrcDir, "merged"))
    if sys.platform.startswith('win'):
        env["LOCALE_MERGEDIR"] = windows2msys(env["LOCALE_MERGEDIR"])
    if sys.platform.startswith('darwin'):
        env["MOZ_PKG_PLATFORM"] = "mac"
    run_cmd(["make", "installers-%s" % locale], cwd=localeSrcDir, env=env)
    retry(run_cmd, args=(["make", "upload", "AB_CD=%s" % locale],),
          kwargs={'cwd': localeSrcDir, 'env': env})

def getLocalesForChunk(possibleLocales, chunks, thisChunk):
    if 'en-US' in possibleLocales:
        possibleLocales.remove('en-US')
    possibleLocales = sorted(possibleLocales)
    nLocales = len(possibleLocales)
    for c in range(1, chunks+1):
        n = nLocales / chunks
        # If the total number of locales isn't evenly divisible by the number
        # of chunks we need to append one more onto some chunks
        if c <= (nLocales % chunks):
            n += 1
        if c == thisChunk:
            return possibleLocales[0:n]
        del possibleLocales[0:n]

def getNightlyLocalesForChunk(appName, sourceRepo, platform, chunks, thisChunk,
                              hg="http://hg.mozilla.org"):
    possibleLocales = getPlatformLocales(
        getAllLocales(appName, sourceRepo, hg=hg),
        (platform,)
    )[platform]
    return getLocalesForChunk(possibleLocales, chunks, thisChunk)
