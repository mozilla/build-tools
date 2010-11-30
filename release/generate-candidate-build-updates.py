#!/usr/bin/python
#
# This script is used to generate updates from all prior builds of the release
# passed to the current one. The procedure is as follows:
#  - Find build info for all prior builds that exist
#  - Find snippets from which to base generated ones on
#  - For each version
#   - For each platform
#    - Create complete snippet
#    - If desired, create partial snippets

from optparse import OptionParser
import os, os.path, shutil, sys
from time import strftime

from release.info import findOldBuildIDs, getBuildID
from release.l10n import getShippedLocales, getCommonLocales
from release.platforms import buildbot2updatePlatform, getPlatformLocales, \
  getSupportedPlatforms

REQUIRED_OPTIONS = ('brandName', 'product', 'appName', 'version', 'oldVersion',
                    'buildNumber', 'oldBuildNumber', 'platforms',
                    'oldBaseSnippetDir', 'sourceRepo', 'workdir', 'hg')
DEFAULT_CHANNELS = ('beta', 'betatest')
DEFAULT_PLATFORMS = getSupportedPlatforms()
DEFAULT_STAGE_SERVER = 'stage.mozilla.org'
DEFAULT_HG_SERVER = 'http://hg.mozilla.org'

def getSnippetDirname(oldBaseSnippetDir, channel):
    if channel == 'release':
        ausdir = 'aus2'
    elif channel.find('test') != -1:
        ausdir = 'aus2.test'
    elif channel == 'beta':
        ausdir = 'aus2.beta'
    else:
        # Total guesswork
        ausdir = 'aus2.%s' % channel
    return os.path.join(oldBaseSnippetDir, ausdir)

def createSnippets(brandName, product, appName, version, oldVersion,
                   buildNumber, oldBuildNumber, platforms, channels,
                   oldBaseSnippetDir, stageServer, hg, sourceRepo,
                   generatePartials, verbose):
    errs = []
    dirs = []
    snippets = ['complete.txt']
    if generatePartials:
        snippets.append('partial.txt')
    previousCandidateIDs = findOldBuildIDs(product, version, buildNumber,
                                           platforms, server=stageServer,
                                           verbose=verbose)
    oldShippedLocales = getShippedLocales(product, appName, oldVersion,
                                          oldBuildNumber, sourceRepo, hg)
    shippedLocales = getShippedLocales(product, appName, version, buildNumber,
                                       sourceRepo, hg)
    for platform in previousCandidateIDs.keys():
        update_platform = buildbot2updatePlatform(platform)
        oldVersionBuildID = getBuildID(platform, product, oldVersion,
                                       oldBuildNumber,
                                       server=stageServer,
                                       verbose=verbose)
        oldPlatformLocales = getPlatformLocales(oldShippedLocales,
                                                (platform,))[platform]
        platformLocales = getPlatformLocales(shippedLocales,
                                             (platform,))[platform]
        commonLocales = getCommonLocales(platformLocales,
                                         oldPlatformLocales)
        for chan in channels:
            baseSnippetDir = getSnippetDirname(oldBaseSnippetDir, chan)
            if not os.path.exists(baseSnippetDir):
                errs.append("Can't generate snippets for %s because %s doesn't exist" % (chan, baseSnippetDir))
                continue
            for buildID in previousCandidateIDs[platform]:
                for locale in commonLocales:
                    try:
                        oldFile = os.path.join(baseSnippetDir, brandName,
                                               oldVersion, update_platform,
                                               oldVersionBuildID, locale, chan,
                                               'complete.txt')
                        oldCompleteSnippet = open(oldFile).read()
                    except Exception, e:
                        errs.append("Error reading from %s\n%s" % \
                          (oldFile, e))
                    newDir = os.path.join(baseSnippetDir, brandName, version,
                                          update_platform, buildID, locale,
                                          chan)
                    try:
                        os.makedirs(newDir)
                        if verbose:
                            "Creating snippets for %s" % newDir
                        for f in snippets:
                            newFile = os.path.join(newDir, f)
                            if verbose:
                                "  %s" % f
                            writeSnippet(newFile, oldCompleteSnippet)
                    except OSError, e:
                        errs.append("Error creating %s\n%s" % (newDir, e))
                    except Exception, e:
                        errs.append("Hit error creating %s\n%s" % \
                          (newFile, e))

                for l in [l for l in platformLocales if l not in commonLocales]:
                    print "WARNING: %s not in oldVersion for %s, did not generate snippets for it" % (l, platform)

    if verbose:
        for e in errs:
            print >>sys.stderr, e
    return len(errs)

def writeSnippet(snippet, contents):
    if os.path.exists(snippet):
        raise Exception("%s already exists, not overwriting" % snippet)
    if snippet.endswith('partial.txt'):
        contents = contents.replace('type=complete', 'type=partial')
    f = open(snippet, 'w')
    f.write(contents)
    f.close()

def getOptions():
    parser = OptionParser()
    parser.add_option("-B", "--brand", dest="brandName", help="Brand Name")
    parser.add_option("-p", "--product", dest="product", help="Product Name")
    parser.add_option("-a", "--app-name", dest="appName", help="App Name")
    parser.add_option("-v", "--version", dest="version", help="Product Version")
    parser.add_option("-o", "--old-version", dest="oldVersion",
                      help="Previous Product Version")
    parser.add_option("-b", "--build-number", dest="buildNumber",
                      help="Current Build of the Product Version")
    parser.add_option("", "--old-build-number", dest="oldBuildNumber",
                      help="Build number of oldVersion")
    parser.add_option("", "--platform", dest="platforms", action="append",
                      default=None,
                      help="Platforms to generate snippets for")
    parser.add_option("-c", "--channel", dest="channels", action="append",
                      default=None,
                      help="Channels to generate snippets for")
    parser.add_option("-s", "--stage-server", dest="stageServer",
                      default=DEFAULT_STAGE_SERVER,
                      help="Server to pull buildids from.")
    parser.add_option("", "--old-base-snippet-dir", dest="oldBaseSnippetDir",
                      help="Directory containing snippets for oldVersion")
    parser.add_option("", "--hg-server", dest="hg", default=DEFAULT_HG_SERVER)
    parser.add_option("", "--source-repo", dest="sourceRepo",
                      help="Source repository, relative to hg host.")
    parser.add_option("-w", "--workdir", dest="workdir",
                      help="Directory to put new snippets in")
    parser.add_option("", "--generate-partials", default=False,
                      action="store_true", dest="generatePartials")
    parser.add_option("", "--verbose", default=False, action="store_true")

    return parser.parse_args()

def validateOptions(options, args):
    errs = ""
    for a in REQUIRED_OPTIONS:
        if not getattr(options, a, None):
            errs += "%s is a required option\n" % a
    if not options.platforms:
        errs += "at least one platform must be provided\n"
    else:
        for p in options.platforms:
            supportedPlatforms = getSupportedPlatforms()
            if not p in supportedPlatforms:
                errs += "%s is not a supported platform\n" % p
    if options.buildNumber < 2:
        errs += "build number must be >= 2\n"
    if errs != "":
        print >>sys.stderr, errs
        sys.exit(1)

def adjustOptions(options, args):
    options.oldBaseSnippetDir = os.path.abspath(options.oldBaseSnippetDir)
    options.buildNumber = int(options.buildNumber)
    options.oldBuildNumber = int(options.oldBuildNumber)
    options.platforms = options.platforms or DEFAULT_PLATFORMS
    options.channels = options.channels or DEFAULT_CHANNELS

def main():
    (options, args) = getOptions()
    validateOptions(options, args)
    adjustOptions(options, args)
    olddir = os.getcwd()
    os.chdir(options.workdir)
    try:
        return createSnippets(options.brandName, options.product,
                              options.appName, options.version,
                              options.oldVersion, options.buildNumber,
                              options.oldBuildNumber, options.platforms,
                              options.channels, options.oldBaseSnippetDir,
                              options.stageServer, options.hg,
                              options.sourceRepo, options.generatePartials,
                              options.verbose)
    finally:
        os.chdir(olddir)

if __name__ == '__main__':
    sys.exit(main())
