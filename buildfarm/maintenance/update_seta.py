from datetime import date
import json
import os
import socket
import urllib2
import shutil
import subprocess
import sys
from sys import path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/python"))

import logging
log = logging.getLogger(__name__)

from util.hg import mercurial, clone, commit, run_cmd

seta_branches = ['mozilla-inbound', 'autoland']

def wfetch(url, retries=5):
    while True:
        try:
            response = urllib2.urlopen(url, timeout=30)
            return json.loads(response.read())
        except urllib2.HTTPError, e:
            log.warning("Failed to fetch '%s': %s" % (url, str(e)))
        except urllib2.URLError, e:
            log.warning("Failed to fetch '%s': %s" % (url, str(e)))
        except socket.timeout, e:
            log.warning("Time out accessing %s: %s" % (url, str(e)))
        except socket.error, e:
            log.warning("Socket error when accessing %s: %s" % (url, str(e)))
        except ValueError, e:
            log.warning("JSON parsing error %s: %s" % (url, str(e)))
        if retries < 1:
            raise Exception("Could not fetch url '%s'" % url)
        retries -= 1
        log.warning("Retrying")
        time.sleep(60)

def update_seta_data(branch, configs_path):
    # For offline work
    if os.environ.get('DISABLE_SETA'):
        return []

    url = "http://alertmanager.allizom.org/data/setadetails/?date=" + today + "&buildbot=1&branch=" + branch + "&inactive=1"
    data = wfetch(url)
    if data:
        temp_file = configs_path + branch + "-seta.json.new"
        existing_file = configs_path + branch + "-seta.json"

        # need to create temp file
        with open(temp_file, 'wt') as f:
            json.dump(data, f, indent=4)
            f.close()
        #rename local files
        os.rename(temp_file, existing_file)
        return True

# main
if __name__ == '__main__':
    from optparse import OptionParser
    from ConfigParser import RawConfigParser
    parser = OptionParser()
    parser.set_defaults(
        loglevel=logging.INFO,
        logfile=None,
    )
    parser.add_option("-l", "--logfile", dest="logfile")
    options, args = parser.parse_args()
    logging.getLogger().setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s - %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    #handler.setLevel(parser.loglevel)
    logging.getLogger().addHandler(handler)

    today = date.today().strftime("%Y-%m-%d")
    remote = "ssh://hg.mozilla.org/build/buildbot-configs"
    ssh_key = "/home/cltbld/.ssh/ffxbld_rsa"
    ssh_username = "ffxbld"
    revision = "default"
    localrepo = "/tmp/buildbot-configs"
    configs_path = localrepo + "/mozilla-tests/"
    msg = "updating seta data for " + today

    if os.path.exists(localrepo):
        oshutil.rmtree(localrepo)
    os.mkdir(localrepo)
    clone(remote, localrepo, revision)
    #assume data could not be fetched
    status = False
    for branch in seta_branches:
        status = update_seta_data(branch, configs_path)
    if not status:
        log.warning("Could not fetch seta data")
    revision = commit(localrepo, msg, user=ssh_username)
    push_cmd = ['hg', 'push']
    push_value = run_cmd(push_cmd, cwd=localrepo)
    if push_value != 0:
        log.warning("Could not push new seta data")
