#! /usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

#
# Script name:   repository_manifest.py
# Author(s):     Zambrano Gasparnian, Armen <armenzg@mozilla.com>
# Target:        Python 2.7.x
#
"""
   Reads a repository manifest and outputs the repo and
   revision/branch in a format digestable for buildbot
   properties ("key: value").
"""
import json
import logging
import urllib2

from optparse import OptionParser

SUCCESS_CODE = 0
# This is not an infra error and we can't recover from
FAILURE_CODE = 1
# When an infra error happens we want to turn purple and
# let sheriffs determine if re-triggering is needed
INFRA_CODE = 3

def main():
    '''
    Determine which repository and revision mozharness.json indicates.
    If none is found we fall back to the default repository
    '''
    parser = OptionParser(__doc__)
    parser.add_option("--manifest-url", dest="manifest_url")
    parser.add_option("--default-repo", dest="default_repo")
    parser.add_option("--default-revision", dest="default_revision")
    parser.add_option("--timeout", dest="timeout", type="float", default=30)
    options, args = parser.parse_args()

    if not options.manifest_url or \
       not options.default_repo or \
       not options.default_revision:
        parser.error("You have to call the script with all options")

    exit_code = FAILURE_CODE
    try:
        url = options.manifest_url
        url_opener = urllib2.urlopen(url, timeout=options.timeout)
        http_code = url_opener.getcode()
        if http_code == 200:
            try:
                manifest = json.load(url_opener)
                repo = manifest["repo"]
                revision = manifest["revision"]
                # Let's determine if the repo and revision exist
                url = '%s/rev/%s' % (repo, revision)
                urllib2.urlopen(url, timeout=options.timeout)
                print "script_repo_url: %s" % repo
                print "script_repo_revision: %s" % revision
                exit_code = SUCCESS_CODE
            except urllib2.HTTPError:
                logging.exception(url)
                exit_code = FAILURE_CODE
            except ValueError:
                logging.exception("We have a non-valid json manifest.")
                exit_code = FAILURE_CODE
        else:
            print "We have failed to retrieve the manifest (http code: %s)" % \
                    http_code
            exit_code = INFRA_CODE

    except urllib2.HTTPError, e:
        if e.getcode() == 404:
            # Fallback to default values for branches where the manifest
            # is not defined
            print "script_repo_url: %s" % options.default_repo
            print "script_repo_revision: %s" % options.default_revision
            exit_code = SUCCESS_CODE
        else:
            logging.exception("We got HTTPError code: %s." % e.getcode())
            exit_code = FAILURE_CODE
    except urllib2.URLError, e:
        logging.exception("URLError for %s" % url)
        exit_code = INFRA_CODE
    except Exception:
        logging.exception("Unknown case")
        exit_code = FAILURE_CODE

    exit(exit_code)

if __name__ == '__main__':
    main()
