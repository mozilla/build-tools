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
import os
import time
import urllib2

from optparse import OptionParser
from ssl import SSLError

SUCCESS_CODE = 0
# This is not an infra error and we can't recover from it
FAILURE_CODE = 1
# When an infra error happens we want to turn purple and
# let sheriffs determine if re-triggering is needed
INFRA_CODE = 3

# Logic based on lib/python/util/retry.py
# The day that we don't wget repository_manifest.py
# we can import directly the functionality
def retry(action, attempts=5, sleeptime=60, max_sleeptime=5 * 60,
          retry_exceptions=(Exception,), cleanup=None, args=(), kwargs={}):
    """Call `action' a maximum of `attempts' times until it succeeds,
        defaulting to 5. `sleeptime' is the number of seconds to wait
        between attempts, defaulting to 60 and doubling each retry attempt, to
        a maximum of `max_sleeptime'.  `retry_exceptions' is a tuple of
        Exceptions that should be caught. If exceptions other than those
        listed in `retry_exceptions' are raised from `action', they will be
        raised immediately. If `cleanup' is provided and callable it will
        be called immediately after an Exception is caught. No arguments
        will be passed to it. If your cleanup function requires arguments
        it is recommended that you wrap it in an argumentless function.
        `args' and `kwargs' are a tuple and dict of arguments to pass onto
        to `callable'"""
    assert callable(action)
    assert not cleanup or callable(cleanup)
    if max_sleeptime < sleeptime:
        logging.debug("max_sleeptime %d less than sleeptime %d" % (
            max_sleeptime, sleeptime))
    n = 1
    while n <= attempts:
        try:
            logging.info("retry: Calling %s with args: %s, kwargs: %s, "
                     "attempt #%d" % (action, str(args), str(kwargs), n))
            return action(*args, **kwargs)
        except retry_exceptions:
            logging.debug("retry: Caught exception: ", exc_info=True)
            if cleanup:
                cleanup()
            if n == attempts:
                logging.info("retry: Giving up on %s" % action)
                raise
            if sleeptime > 0:
                logging.info(
                    "retry: Failed, sleeping %d seconds before retrying" %
                    sleeptime)
                time.sleep(sleeptime)
                sleeptime = sleeptime * 2
                if sleeptime > max_sleeptime:
                    sleeptime = max_sleeptime
            continue
        finally:
            n += 1

def main():
    '''
    Determine which repository and revision mozharness.json indicates.
    If none is found we fall back to the default repository
    '''
    parser = OptionParser(__doc__)
    parser.add_option("--manifest-url", dest="manifest_url",
                     help="URL to json file which specifies 'repo' and "
                      "'revision' values.")
    parser.add_option("--default-repo", dest="default_repo",
                     help="If manifest_url is a 404 this is the repository we "
                      "default to.")
    parser.add_option("--default-revision", dest="default_revision",
                     help="If manifest_url is a 404 this is the revision we "
                      "default to.")
    parser.add_option("--default-checkout", dest="default_checkout",
                     help="If manifest_url's repo is the same as default_repo "
                      "then use the default_checkout, otherwise, use checkout."
                      "This is an optimization for when we have the ability "
                      "of using an hg-shared checkout.")
    parser.add_option("--checkout", dest="checkout",
                     help="If default_repo and the repo in manifest_url are "
                     "distinct we use a different checkout. In other words, "
                     "we don't want to use an hg-shared checkout since we're "
                     "trying to checkout a complete different repository")
    parser.add_option("--timeout", dest="timeout", type="float", default=30,
                     help="Used to specify how long to wait until timing out "
                      "for network requests.")
    parser.add_option("--max-retries", dest="max_retries", type="int",
                      default=10,
                     help="A maximum number of retries for network requests.")
    parser.add_option("--sleeptime", dest="sleeptime", type="int", default=10,
                     help="How long to sleep in between network requests.")
    options, args = parser.parse_args()

    if not options.manifest_url or \
       not options.default_repo or \
       not options.default_revision:
        parser.error("You have to call the script with all options")

    if options.default_checkout and options.checkout \
       and options.default_checkout == options.checkout:
        parser.error("If you use --default-checkout and --checkout,"
                     "you can't have them be the same value.")

    exit_code = FAILURE_CODE
    try:
        url = options.manifest_url
        url_opener = retry(
            urllib2.urlopen,
            attempts=options.max_retries,
            sleeptime=options.sleeptime,
            max_sleeptime=options.max_retries * options.sleeptime,
            retry_exceptions=(
                SSLError,
                urllib2.URLError,
            ),
            args=(url, ),
            kwargs={
                "timeout": options.timeout,
            },
        )
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
                # This block allow us to take advantage of default shared
                # checkouts
                if options.default_checkout and options.checkout:
                    if options.default_repo == repo:
                        # In the manifest we've requested to checkout the defult
                        # repo, hence, we will use the default_checkout
                        # location in order to use the hg-shared checkout
                        checkout = options.default_checkout
                    else:
                        # We are not requesting the default repository, hence,
                        # we can't use the hg-shared checkout
                        checkout = options.checkout

                    if not os.path.exists(checkout):
                        print "The specified checkout (%s) does not exist." % checkout
                        exit_code = FAILURE_CODE
                    else:
                        print "script_repo_checkout: %s" % checkout

            except urllib2.HTTPError:
                # This is a 404 case because either the repo or the
                # revision have wrong values
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
            if options.default_checkout:
                if not os.path.exists(checkout):
                    print "The specified checkout (%s) does not exist." % checkout
                    exit_code = FAILURE_CODE
                else:
                    print "script_repo_checkout: %s" % options.default_checkout
            exit_code = SUCCESS_CODE
        else:
            logging.exception("We got HTTPError code: %s." % e.getcode())
            exit_code = FAILURE_CODE
    except SSLError:
        logging.exception("SSLError for %s" % url)
        exit_code = INFRA_CODE
    except urllib2.URLError:
        logging.exception("URLError for %s" % url)
        exit_code = INFRA_CODE
    except Exception:
        logging.exception("Unknown case")
        exit_code = FAILURE_CODE

    exit(exit_code)

if __name__ == '__main__':
    main()
