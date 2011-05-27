#!/usr/bin/env python

# generate android snippets.
# standard mozilla tri-license applies
# originally written by John Ford in May 2011

import hashlib
import ConfigParser
import urllib2
import optparse
import os
import os.path as path
import zipfile
from StringIO import StringIO # Needed until we move to python2.6
#import subprocess as s
import sys
import logging

sys.path.append(path.join(path.dirname(__file__), "../../lib/python"))
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

from util.commands import run_cmd
from util.commands import run_remote_cmd

def flush():
    log.debug('flushing stdout/stderr')
    sys.stdout.flush()
    sys.stderr.flush()

def hashFile(filename, hash_type):
    '''Return the 'hash_type' hash of a file at 'filename' '''
    h = hashlib.new(hash_type)
    f = open(filename, "rb")
    while True:
        data = f.read(1024)
        if not data:
            break
        h.update(data)
    f.close()
    hash = h.hexdigest()
    log.info('hash of type %s for file %s is %s' % (hash_type,filename,hash))
    return hash


def ssh(host, command, user=None, key=None):
    '''Abstract ssh into a python function'''
    flush()
    run_remote_cmd(command, host, user, key)
    flush()


def _scp(host, key=None, src=[], dest=None):
    '''Internal abstraction of the scp command into a python
    function'''
    assert dest, 'Must specify destination files for scp'
    cmd = ['scp']
    if key:
        cmd += ['-i', os.path.expanduser(key)]
    for i in src:
        cmd.append(i)
    cmd.append(dest)
    flush()
    run_cmd(cmd)
    flush()


def _scp_file(filename, host, user=None):
    '''Internal function to convert into user@host:file notation'''
    if user:
        return '%s@%s:%s' % (user, host, filename)
    else:
        return '%s:%s' % (host, filename)


def scp_in(host, user=None, key=None, src=[], dest=None):
    '''Copy a file from host to local machine'''
    return _scp(host, key, user,
        [_scp_file(x,host,user) for x in src],dest)


def scp_out(host, user=None, key=None, src=[], dest=None):
    '''Copy file to a remote machine from local machine'''
    return _scp(host, key, src, _scp_file(dest, host, user))


def parseApk(apk_filename):
    '''Take an APK file and figure out the buildid and version from
    the contained application.ini file.'''
    # the ZipFile.open call depends on py2.6 but removes the dependency
    # on StringIO
    #appini = zipfile.ZipFile(apk_filename).open('application.ini', 'r')
    appini = StringIO(zipfile.ZipFile(apk_filename).read('application.ini'))
    config = ConfigParser.ConfigParser()
    config.readfp(appini)

    info = {}

    buildid = config.get('App', 'BuildID')
    version = config.get('App', 'Version')

    appini.close()

    log.info('Build ID for %s is %s' % (apk_filename, buildid))
    log.info('Version for %s is %s' % (apk_filename, version))

    return (buildid, version)


def generateCompleteSnippet(apk_filename, buildid, version, hash_type,
        download_base_url, download_subdir, distdir, topsrcdir, output_filename,):
    '''Generate a complete snippet using provided information and write that snippet
       to a file specified by 'output_filename'
    '''
    output_file = open(output_filename, 'wb+')

    filesize = os.path.getsize(apk_filename)

    hash = hashFile(apk_filename, hash_type)

    # from buildbotcustom.steps.update.CreateUpdateSnippet
    year = buildid[0:4]
    month = buildid[4:6]
    day = buildid[6:8]
    hour = buildid[8:10]
    dateddir = '%s/%s/%s-%s-%s-%s' % (year, month, year, month,
                                         day, hour)

    # Could probably implement this more cleanly
    print >>output_file, 'version=1'
    print >>output_file, 'type=complete'
    print >>output_file, 'url=%s/nightly/%s-%s/%s' % \
            (download_base_url.rstrip('/'), dateddir,
             download_subdir, os.path.basename(apk_filename.rstrip('/')))
    print >>output_file, 'hashFunction=%s' % hash_type
    print >>output_file, 'hashValue=%s' % hash
    print >>output_file, 'size=%s' % filesize
    print >>output_file, 'build=%s' % buildid
    print >>output_file, 'appv=%s' % version
    print >>output_file, 'extv=%s' % version
    output_file.close()
    f=open(output_filename)
    log.info('complete snippet: |%s|' % r'\n'.join([x.strip('\n') for x in f.readlines()]))
    f.close()
    assert os.path.exists(output_filename)


def generatePartialSnippet(apk_filename, buildid, version, hash_type,
        download_base_url, download_subdir, distdir, topsrcdir, output_filename):
    """This function is pretty bare because we don't currently do partials.
    This is done instead of touch over ssh to allow for future partial generation
    with minimal effort"""
    output_file = open(output_filename, 'wb+')
    output_file.close()
    assert os.path.exists(output_filename)


def createAusUploadDirectory(aus_host, aus_user, aus_key, aus_directory):
    """Ensure that the directory specified exists on the aus host"""
    ssh(aus_host, ['mkdir', '-p', aus_directory], aus_user, aus_key)


def getPreviousBuildID(download_base_url, download_subdir):
    """Figure out what the previous buildid is"""
    if os.path.exists('previous.apk'):
        os.remove('previous.apk')
    run_cmd(['wget', '-O', 'previous.apk',
         '%s/nightly/latest-%s/gecko-unsigned-unaligned.apk' % (download_base_url, download_subdir)])
    return parseApk('previous.apk')[0]


def transferSnippets(aus_host, aus_user, aus_key, snippets, snippet_directory):
    """Upload snippets to aus host"""
    scp_out(aus_host, aus_user, aus_key, snippets, snippet_directory)


def createEmptySnippets(aus_host, aus_user, aus_key, sd, snip):
    """ Create a set of empty snippets.  Not sure why, but this is needed"""
    ssh(aus_host, 'touch %s %s' % (' '.join(['%s/%s' % (sd,x) for x in snip]),sd),
        aus_user, aus_key)


def uploadSnippets( aus_host, aus_user, aus_key, aus_base,
            abi, locale, old_buildid, new_buildid, snippets):
    snippet_directory = '%s/%s/%s/%s' % (aus_base, abi, old_buildid, locale)
    empty_snippet_directory = '%s/%s/%s/%s' % (aus_base, abi, new_buildid, locale)
    createAusUploadDirectory(aus_host, aus_user, aus_key, snippet_directory)
    transferSnippets(aus_host, aus_user, aus_key, snippets, snippet_directory)
    createAusUploadDirectory(aus_host, aus_user, aus_key, empty_snippet_directory)
    createEmptySnippets(aus_host, aus_user, aus_key, empty_snippet_directory, snippets)


def main():
    parser = optparse.OptionParser()
    # These defaults are set for android
    parser.add_option('--hash', dest='hash_type', default='sha512')
    parser.add_option('--distdir', dest='distdir', default='obj-firefox/dist')
    parser.add_option('--srcdir', dest='topsrcdir', default='.')
    parser.add_option('--abi', dest='abi')
    parser.add_option('--locale', dest='locale', default='en-US')
    parser.add_option('--aus-host', dest='aus_host')
    parser.add_option('--aus-user', dest='aus_user')
    parser.add_option('--aus-ssh-key', dest='aus_key')
    parser.add_option('--aus-base-path', dest='aus_base')
    parser.add_option('--download-base-url', dest='download_base_url')
    parser.add_option('--download-subdir', dest='download_subdir',
                      help='something like mozilla-central-android')
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true')
    (options, args) = parser.parse_args()
    assert options.download_base_url
    assert options.download_subdir
    assert options.abi
    assert options.aus_base
    assert options.aus_host
    assert options.aus_user
    assert options.aus_key
    assert len(args) is 1

    if options.verbose:
        log.setLevel(logging.DEBUG)

    try:
        hashlib.new(options.hash_type)
    except:
        log.error('hash "%s" not available' % options.hash_type)
        exit(1)

    new_buildid, version = parseApk(args[0])
    old_buildid = getPreviousBuildID(options.download_base_url,
                                     options.download_subdir)
    generateCompleteSnippet(args[0], new_buildid, version, options.hash_type,
            options.download_base_url, options.download_subdir, options.distdir,
            options.topsrcdir, 'complete.txt')
    generatePartialSnippet(args[0], new_buildid, version, options.hash_type,
            options.download_base_url, options.download_subdir, options.distdir,
            options.topsrcdir, 'partial.txt')
    uploadSnippets(options.aus_host, options.aus_user, options.aus_key,
                   options.aus_base, options.abi, options.locale, old_buildid,
                   new_buildid, ['complete.txt', 'partial.txt'])


if __name__ == '__main__':
    main()
