#!/usr/bin/env python

import copy
import os
import sys
import re

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/python"))
from build.versions import increment
from release.info import readReleaseConfig


def bumpReleaseconfig(releaseConfigFile, options):
    processVars = ['buildNumber', ]
    build1BumpVars = ['version', 'baseTag', 'nextAppVersion', 'nextMilestone']
    build1ProcessVars = ['oldVersion', 'oldBuildNumber', 'oldBaseTag']

    oldReleaseConfig = readReleaseConfig(releaseConfigFile)
    newReleaseConfig = copy.copy(oldReleaseConfig)
    dictVars = {}

    if options.bumpVersion:
        newReleaseConfig['buildNumber'] = 1
        for param in build1BumpVars:
            newReleaseConfig[param] = increment(oldReleaseConfig[param])
        if not options.preserve_relbranch:
            dictVars['relbranch'] = None
        newReleaseConfig['oldVersion'] = oldReleaseConfig['version']
        newReleaseConfig['oldBuildNumber'] = oldReleaseConfig['buildNumber']
        newReleaseConfig['oldBaseTag'] = oldReleaseConfig['baseTag']
        processVars.extend(build1ProcessVars + build1BumpVars)
    else:
        newReleaseConfig['buildNumber'] = oldReleaseConfig['buildNumber'] + 1
        if newReleaseConfig['buildNumber'] == 2:
            if not options.relbranch:
                print "Error: relbranch is required for build2!"
                sys.exit(2)
            else:
                dictVars['relbranch'] = options.relbranch

    if not options.revision:
        print "Error: revision is required!"
        sys.exit(3)
    else:
        dictVars['revision'] = options.revision

    processFile(releaseConfigFile, processVars, dictVars, newReleaseConfig)


def processFile(releaseConfigFile, processVars, dictVars, newReleaseConfig):
    newReleaseConfigFile = releaseConfigFile + '.tmp'
    t = open(newReleaseConfigFile, 'w')
    for l in open(releaseConfigFile).readlines():
        for var in processVars:
            # releaseConfig['%s'] style vars
            s = "releaseConfig['%s']" % var
            if l.lstrip().startswith(s):
                k = l.split('=')[0]
                l = '%s= %s\n' % (k, repr(newReleaseConfig[var]))
        for name, value in dictVars.items():
            search_re = r'\s*[\'"]%s[\'"][\s]*:[\s]*' % name
            if re.search(search_re, l):
                l = re.sub(':.*', ': %s,' % repr(value), l)
        t.write(l)
    t.close()
    os.rename(newReleaseConfigFile, releaseConfigFile)

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(usage='usage: %prog [options] file')

    parser.add_option("-r", "--revision", dest="revision",
                      help="Release revision")
    parser.add_option("-v", "--bump-version", dest="bumpVersion",
                      action="store_true", default=False,
                      help="Bump version instead of build number")
    parser.add_option("-b", "--relbranch", dest="relbranch",
                      help="Relbranch name. Mandatory for build2.")
    parser.add_option("-c", "--preserve-relbranch", dest="preserve_relbranch",
                      action="store_true", default=False,
                      help="Don't alter relbranch. Useful for chemspills.")

    options, args = parser.parse_args()
    if not args:
        parser.error(parser.get_usage())
    for releaseConfigFile in args:
        bumpReleaseconfig(releaseConfigFile, options)
