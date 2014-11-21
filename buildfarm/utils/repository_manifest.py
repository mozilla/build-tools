#! /usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

#
# Script name:   repository_manifest.py
# Author(s):     Zambrano Gasparnian, Armen <armenzg@mozilla.com>
# Target:        Python 2.7.x
#
"""Reads a repository manifest and outputs the repo and
revision/branch in a format digestable for buildbot
properties: "key: value"
"""
import argparse
import json
import urllib2

# When an infra error happens we want to turn purple and
# let sheriffs determine if re-triggering is needed
INFRA_CODE = 3

def main():
    '''
    Determine which repository and revision mozharness.json indicates.
    If none is found we fall back to the default repository
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-url", dest="manifest_url", required=True)
    parser.add_argument("--default-repo", dest="default_repo", required=True)
    parser.add_argument("--default-revision", dest="default_revision",
                        required=True)
    args = parser.parse_args()

    exit_code = 0
    try:
        url_opener = urllib2.urlopen(args.manifest_url, timeout=10)
        http_code = url_opener.getcode()
        if http_code == 200:
            manifest = json.load(url_opener)
            print "script_repo_url: %s" % manifest["repo"]
            print "script_repo_revision: %s" % manifest["revision"]
            exit_code = 0
        else:
            print "We have failed to retrieve the manifest (http code: %s)" % \
                    http_code
            exit_code = INFRA_CODE
    except urllib2.HTTPError, e:
        # Fallback to default values for branches where the manifest
        # is not defined
        print "script_repo_url: %s" % args.default_repo
        print "script_repo_revision: %s" % args.default_revision
        exit_code = 0
    except Exception, e:
        print str(e)
        exit_code = INFRA_CODE

    exit(exit_code)

if __name__ == '__main__':
    main()
