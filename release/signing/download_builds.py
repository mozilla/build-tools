#!/usr/bin/env python
""" Usage: %prog [-p|--product] [-l|--hgurl] version unsigned-dir
ssh_key stage-username stage-host release-config

Script runs `make download` continuously in a loop until it has determined
that all signing deliverables it needs have been downloaded """

import os, subprocess, time
import logging
from optparse import OptionParser
from release.platforms import getPlatformLocales
from release.l10n import getShippedLocales
from release.download import expectedFiles
from release.info import readReleaseConfig
log = logging.getLogger()

# Explicit list of what platform deliverables are downloaded to each signing
# platform
download_platform_map = {
    'win32' : ('win32', 'win64', 'linux', 'linux64'),
    'mac'   : ('macosx', 'macosx64'),
}

def check_source_bundle(unsigned_dir):
    """ Check if the source bundle and tarball is present in the signing
    directory """
    source_dir = os.path.join(unsigned_dir, 'source')
    if os.path.isdir(source_dir):
        return len([f for f in os.listdir(source_dir)
            if f.endswith('.bundle') or f.endswith('source.tar.bz2')]) == 2

def check_unsigned_dir(unsigned_dir, platform_locales, allplatforms, signed_platforms,
        partner_repacks):
    """ Check to see if we've finished downloading all locales and partners
    for all platforms to the unsigned dir
    Also check for:
    - *_info.txt for for all platforms
    - partner-repacks for all platforms
    - source bundle/tarball
    """
    # Only check the source bundle on one platform. If we have more than one
    # platform we sign on, we should avoid downloading and re-signing the
    # source bundle
    if 'win32' in allplatforms:
        if not check_source_bundle(unsigned_dir):
            log.error("Missing source bundles")
            return False
    # check partner repacks and info.txt files
    for platform in allplatforms:
        unsigned = 'unsigned' if platform in signed_platforms else ''
        if not os.path.exists(os.path.join(
            unsigned_dir, unsigned,
            '%s_info.txt' % platform)):
            log.error("Missing info files")
            return False
        if partner_repacks and not os.path.exists(os.path.join(
            unsigned_dir,
            'unsigned/partner-repacks',
            'partner_build_%s' % platform)):
            log.error("Missing partner repack file: partner_build_%s" % platform)
            return False

    # check for packages, MARs and xpis.
    for platform in platform_locales.keys():
        for locale in platform_locales[platform]:
            if not expectedFiles(unsigned_dir, locale, platform, signed_platforms):
                log.error("Missing repack for platform & locale %s/%s" % (platform, locale))
                return False
    return True

def extract_config_info(release_config_url):
    """ Grab the contents of release configs to construct a URL to
    shipped_locales """
    log.info("Grabbing release configs from %s", release_config_url)
    try:
        subprocess.check_call(['wget',
            '-O', './release_config.py',
            release_config_url])
    except subprocess.CalledProcessError:
        log.fatal("error grabbing release configs")
        raise
    log.info("Attempting to import release_config.py...")
    return readReleaseConfig('release_config.py')

def download_builds(ssh_key, stage_username, stage_host, release_config):
    """ Download the builds from stage """
    try:
        # Download the builds.
        command = ['make', 'download',
            'SSH_KEY=%s' % ssh_key,
            'STAGE_USERNAME=%s' % stage_username,
            'STAGE_HOST=%s' % stage_host,
            'PRODUCT=%s' % release_config['productName'],
            'VERSION=%s' % release_config['version'],
            'BUILD=%s' % release_config['buildNumber'],
        ]
        log.debug(command)
        os.putenv("SKIP_PASS", "1")
        subprocess.check_call(command)
    except subprocess.CalledProcessError:
        log.error("Unable to download builds!")

def main():
    """ Parse options and run download loop """
    parser = OptionParser(__doc__)
    parser.set_defaults(
        product="firefox",
        hgurl="http://hg.mozilla.org",
        repo_path="build/buildbot-configs",
        source_repo_key="mozilla"
    )
    parser.add_option("-p", "--product", dest="product", help="product name")
    parser.add_option("-r", "--repo-path", dest="repo_path",
        help="configs repo path")
    parser.add_option("-l", "--hgurl", dest="hgurl", help="hg URL prefix")
    parser.add_option("-P", "--platform", dest="platform",
        help="platform being signed on")
    parser.add_option("--source-repo-key", dest="source_repo_key",
        help="Which sourceRepository entry to pull sourceRepoPath from")
    parser.add_option("-V", "--verify", dest="verify", action="store_true",
        help="Just verify that the deliverables are present")
    options, args = parser.parse_args()
    if len(args) < 6:
        parser.error("")
    version = args[0]
    unsigned_dir = args[1]
    ssh_key = args[2]
    stage_username = args[3]
    stage_host = args[4]
    release_config_file = args[5]

    prefix = "%s/%s/raw-file/%s_%s_RELEASE/%s"
    release_config_url = prefix % (
            options.hgurl,
            options.repo_path,
            options.product.upper(),
            version.replace(".", "_"),
            release_config_file,
        )
    release_config = extract_config_info(release_config_url)
    allplatforms = release_config['enUSPlatforms']

    # If we explicitly specify the platform we're signing on, use the
    # download_platform_map to count the other platform deliverables that
    # will be downloaded and signed on this signing platform
    if options.platform:
        # only look at platforms that are also in the release configs
        allplatforms = [p for p in download_platform_map[options.platform]
            if p in release_config['enUSPlatforms']]
        log.info("Looking for builds on : %s" % allplatforms)

    platform_locales = getPlatformLocales(getShippedLocales(
            release_config['productName'],
            release_config['appName'],
            release_config['version'],
            release_config['buildNumber'],
            release_config['sourceRepositories'][options.source_repo_key]['path'],
            options.hgurl),
        allplatforms)

    if options.verify:
        if not check_unsigned_dir(
            unsigned_dir,
            platform_locales,
            allplatforms,
            release_config.get('signedPlatforms', ('win32',)),
            release_config['doPartnerRepacks']):
            log.fatal("Error, missing signing deliverables")
            exit(1)
        else:
            log.info("All Deliverables Present")
            exit()

    while not check_unsigned_dir(
            unsigned_dir,
            platform_locales,
            allplatforms,
            release_config.get('signedPlatforms', ('win32',)),
            release_config['doPartnerRepacks']):
        download_builds(ssh_key, stage_username, stage_host, release_config)
        time.sleep(10)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s : %(levelname)s: %(message)s")
    main()
