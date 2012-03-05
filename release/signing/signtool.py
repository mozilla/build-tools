#!/usr/bin/python
"""signtool.py [options] file [file ...]

If no include patterns are specified, all files will be considered. -i/-x only
have effect when signing entire directories."""
import os
import sys, site
# Modify our search path to find our modules
site.addsitedir(os.path.join(os.path.dirname(__file__), "../../lib/python"))

import logging
from signing import remote_signfile, find_files, buildValidatingOpener
log = logging.getLogger(__name__)

import pefile

def is_authenticode_signed(filename):
    """Returns True if the file is signed with authenticode"""
    p = None
    try:
        p = pefile.PE(filename)
        # Look for a 'IMAGE_DIRECTORY_ENTRY_SECURITY' entry in the optinal data directory
        for d in p.OPTIONAL_HEADER.DATA_DIRECTORY:
            if d.name == 'IMAGE_DIRECTORY_ENTRY_SECURITY' and d.VirtualAddress != 0:
                return True
        return False
    except:
        log.exception("Problem parsing file")
        return False
    finally:
        if p:
            p.close()

def main():
    from optparse import OptionParser
    import random
    parser = OptionParser(__doc__)
    parser.set_defaults(
            hosts=[],
            cert=None,
            log_level=logging.INFO,
            output_dir=None,
            output_file=None,
            formats=[],
            includes=[],
            excludes=[],
            nsscmd=None,
            tokenfile=None,
            noncefile=None,
            cachedir=None,
            )

    parser.add_option("-H", "--host", dest="hosts", action="append", help="hostname[:port]")
    parser.add_option("-c", "--server-cert", dest="cert")
    parser.add_option("-t", "--token-file", dest="tokenfile", help="file where token is stored")
    parser.add_option("-n", "--nonce-file", dest="noncefile", help="file where nonce is stored")
    parser.add_option("-d", "--output-dir", dest="output_dir",
            help="output directory; if not set then files are replaced with signed copies")
    parser.add_option("-o", "--output-file", dest="output_file",
            help="output file; if not set then files are replaced with signed copies. This can only be used when signing a single file")
    parser.add_option("-f", "--formats", dest="formats", action="append",
            help="signing formats (one or more of \"signcode\", \"gpg\", or \"osx\")")
    parser.add_option("-q", "--quiet", dest="log_level", action="store_const",
            const=logging.WARN)
    parser.add_option("-v", "--verbose", dest="log_level", action="store_const",
            const=logging.DEBUG)
    parser.add_option("-i", "--include", dest="includes", action="append",
            help="add to include patterns")
    parser.add_option("-x", "--exclude", dest="excludes", action="append",
            help="add to exclude patterns")
    parser.add_option("--nsscmd", dest="nsscmd",
            help="command to re-sign nss libraries, if required")
    parser.add_option("--cachedir", dest="cachedir",
            help="local cache directory")
    # TODO: Concurrency?
    # TODO: Different certs per server?

    options, args = parser.parse_args()

    logging.basicConfig(level=options.log_level, format="%(asctime)s - %(message)s")

    if not options.hosts:
        parser.error("at least one host is required")

    if not options.cert:
        parser.error("certificate is required")

    if not os.path.exists(options.cert):
        parser.error("certificate not found")

    if not options.tokenfile:
        parser.error("token file is required")

    if not options.noncefile:
        parser.error("nonce file is required")

    # Covert nsscmd to win32 path if required
    if sys.platform == 'win32' and options.nsscmd:
        nsscmd = options.nsscmd.strip()
        if nsscmd.startswith("/"):
            drive = nsscmd[1]
            options.nsscmd = "%s:%s" % (drive, nsscmd[2:])

    # Handle format
    formats = []
    allowed_formats = ("signcode", "gpg", "mar")
    for fmt in options.formats:
        if "," in fmt:
            for fmt in fmt.split(","):
                if fmt not in allowed_formats:
                    parser.error("invalid format: %s", fmt)
                formats.append(fmt)
        elif fmt not in allowed_formats:
            parser.error("invalid format: %s", fmt)
        else:
            formats.append(fmt)

    if options.output_file and (len(args) > 1 or os.path.isdir(args[0])):
        parser.error("-o / --output-file can only be used when signing a single file")

    if options.output_dir:
        if os.path.exists(options.output_dir):
            if not os.path.isdir(options.output_dir):
                parser.error("output_dir (%s) must be a directory", options.output_dir)
        else:
            os.makedirs(options.output_dir)

    if not options.includes:
        # Do everything!
        options.includes.append("*")

    if not formats:
        parser.error("no formats specified")

    buildValidatingOpener(options.cert)

    urls = ["https://%s" % host for host in options.hosts]
    random.shuffle(urls)

    log.debug("in %s", os.getcwd())

    token = open(options.tokenfile, 'rb').read()

    for fmt in formats:
        log.debug("doing %s signing", fmt)
        files = find_files(options, args)
        for f in files:
            log.debug("%s", f)
            log.debug("checking %s for signature...", f)
            if fmt == 'signcode' and is_authenticode_signed(f):
                log.info("Skipping %s because it looks like it's already signed", f)
                continue
            for url in urls[:]:
                if options.output_dir:
                    dest = os.path.join(options.output_dir, os.path.basename(f))
                else:
                    dest = None

                if remote_signfile(options, url, f, fmt, token, dest):
                    break
                elif len(urls) > 1:
                    # Move the url to the end of the list
                    urls.remove(url)
                    urls.append(url)
            else:
                log.error("Failed to sign %s with %s", f, fmt)
                sys.exit(1)

        if fmt == "dmg":
            for fd in args:
                log.debug("unpacking %s", fd)
                unpacktar(fd+'.tar', os.getcwd())
                os.unlink(fd+'.tar')


if __name__ == '__main__':
    main()
