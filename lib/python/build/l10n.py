import os, sys
from os import path
import shutil

from util.commands import run_cmd
from util.hg import mercurial, update
from util.paths import windows2msys

import logging
log = logging.getLogger(__name__)

def compareLocales(repo, locale, l10nRepoDir, localeSrcDir, l10nIni,
                   revision="default", merge=True):
    mercurial(repo, "compare-locales")
    update("compare-locales", revision=revision)
    run_cmd(["python", path.join("compare-locales", "scripts",
                                 "compare-locales"),
             "-m", path.join(localeSrcDir, "merged"),
             l10nIni,
             l10nRepoDir, locale],
             env={"PYTHONPATH": path.join("compare-locales", "lib")})

def l10nRepackPrep(sourceRepo, sourceRepoName, revision, objdir,
                   mozconfigPath, l10nBaseRepoName, makeDirs, localeSrcDir,
                   env):
    if not path.exists(l10nBaseRepoName):
        os.mkdir(l10nBaseRepoName)
    mercurial(sourceRepo, sourceRepoName)
    update(sourceRepoName, revision=revision)
    shutil.copy(mozconfigPath, path.join(sourceRepoName, ".mozconfig"))
    run_cmd(["make", "-f", "client.mk", "configure"], cwd=sourceRepoName,
            env=env)
    for dir in makeDirs:
        run_cmd(["make"], cwd=path.join(sourceRepoName, objdir, dir), env=env)

def repackLocale(locale, l10nRepoDir, l10nBaseRepo, revision, localeSrcDir,
                 l10nIni, compareLocalesRepo, env, merge=True):
    repo = "/".join([l10nBaseRepo, locale])
    localeDir = path.join(l10nRepoDir, locale)
    mercurial(repo, localeDir)
    update(localeDir, revision=revision)
    
    compareLocales(compareLocalesRepo, locale, l10nRepoDir, localeSrcDir,
                   l10nIni, revision=revision, merge=merge)
    env["AB_CD"] = locale
    env["LOCALE_MERGEDIR"] = path.abspath(path.join(localeSrcDir, "merged"))
    if sys.platform.startswith('win'):
        env["LOCALE_MERGEDIR"] = windows2msys(env["LOCALE_MERGEDIR"])
    run_cmd(["make", "installers-%s" % locale], cwd=localeSrcDir, env=env)
    run_cmd(["make", "l10n-upload-%s" % locale], cwd=localeSrcDir, env=env)
