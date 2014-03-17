import logging
from os import makedirs, mkdir, path
import site
import sys

site.addsitedir(path.join(path.dirname(__file__), "../../lib/python"))
site.addsitedir(path.join(path.dirname(__file__), "../../lib/python/vendor"))

import requests

from build.checksums import parseChecksumsFile
from release.updates.patcher import PatcherConfig, substitutePath
from release.updates.snippets import createSnippet, getSnippetPaths

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser("")

    parser.add_option("-c", "--config", dest="config")
    parser.add_option("--snippet-dir", dest="snippet_dir", default="aus2")
    parser.add_option(
        "--test-snippet-dir", dest="test_snippet_dir", default="aus2.test")
    parser.add_option("--hash-type", dest="hashType", default="sha512")
    parser.add_option(
        "--checksums-dir", dest="checksumsDir", default="checksums")
    parser.add_option(
        "-v", "--verbose", dest="verbose", default=False, action="store_true")

    options, args = parser.parse_args()

    if not options.config:
        print >>sys.stderr, "Required option --config not present"
        sys.exit(1)

    log_level = logging.INFO
    if options.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(name)s.%(funcName)s#%(lineno)s: %(message)s")
    log = logging.getLogger()

    hashType = options.hashType.lower()
    pc = PatcherConfig(open(options.config).read())
    appName = pc['appName']
    version = pc['current-update']['to']
    appVersion = pc['release'][version]['extension-version']
    prettyVersion = pc['release'][version]['prettyVersion']

    # We end up using most checksums many times so we keep an in-memory
    # cache of them to speed things up. We also keep an on-disk cache
    # of the downloaded .checksums files in checksumsDir to speed things up
    # if we have to re-run the script for some reason.
    checksums = {}
    checksumsDir = options.checksumsDir
    if not path.exists(checksumsDir):
        mkdir(checksumsDir)

    def cacheChecksums(platform, locale, sums):
        if platform not in checksums:
            checksums[platform] = {}
        checksums[platform][locale] = sums

    # We use both an on-disk and in-memory cache of checksums to speed up
    # the snippet creation process. In order, we try to:
    # - Look for the checksums in the in-memory cache
    # - Read the checksums from the on-disk cache
    # - Download a fresh copy of the checksums file and cache both places.
    def getChecksum(platform, locale, checksumsFile):
        if checksums.get(platform, {}).get(locale):
            log.debug(
                "Using in-memory checksums for %s %s" % (platform, locale))
        else:
            try:
                cacheChecksums(platform, locale,
                               parseChecksumsFile(open(checksumsFile).read()))
                log.debug(
                    "Using on-disk checksums for %s %s" % (platform, locale))
            except (IOError, ValueError):
                contents = requests.get(
                    checksumsUrl, config={'danger_mode': True}).content
                log.debug("Using newly downloaded checksums for %s %s" %
                          (platform, locale))
                # Cache the sums in-memory and on-disk.
                cacheChecksums(platform, locale, parseChecksumsFile(contents))
                with open(checksumsFile, 'w') as f:
                    f.write(contents)
        return checksums[platform][locale]

    for fromVersion, platform, locale, channels, updateTypes in pc.getUpdatePaths():
        fromRelease = pc['release'][fromVersion]
        buildid = pc['release'][version]['platforms'][platform]
        fromBuildid = fromRelease['platforms'][platform]
        fromAppVersion = fromRelease['extension-version']
        detailsUrl = substitutePath(
            pc['current-update']['details'], platform, locale, appVersion)
        optionalAttrs = pc.getOptionalAttrs(fromVersion, locale)
        checksumsUrl = substitutePath(
            pc['release'][version]['checksumsurl'], platform, locale)
        checksumsFile = path.join(options.checksumsDir, "%s-%s-%s-%s" %
                                  (appName, platform, locale, version))

        info = getChecksum(platform, locale, checksumsFile)
        # We may have multiple update types to generate a snippet for...
        for type_ in updateTypes:
            # And also multiple channels...
            for channel in channels:
                log.debug("Processing: %s %s %s %s %s" % (
                    fromVersion, platform, locale, channel, type_))
                url = pc.getUrl(fromVersion, platform, locale, type_, channel)
                filename = path.basename(
                    pc.getPath(fromVersion, platform, locale, type_))
                for f in info:
                    if filename == path.basename(f):
                        hash_ = info[f]['hashes'][hashType]
                        size = info[f]['size']
                        break
                else:
                    raise Exception("Couldn't find hash/size, bailing")
                # We also may have multiple snippets for the same platform.
                for snippet in getSnippetPaths(pc['appName'], fromAppVersion, platform, fromBuildid, locale, channel, type_):
                    if channel in pc['current-update']['channel']:
                        snippet = path.join(options.snippet_dir, snippet)
                    else:
                        snippet = path.join(options.test_snippet_dir, snippet)
                    contents = createSnippet(fromRelease['schema'], type_, url, hash_, size, buildid, prettyVersion, appVersion, detailsUrl, hashType, **optionalAttrs)
                    log.info("Writing snippet: %s" % snippet)
                    if not path.exists(path.dirname(snippet)):
                        makedirs(path.dirname(snippet))
                    with open(snippet, 'w') as f:
                        f.write(contents)
