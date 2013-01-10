import logging
import re
from util.commands import run_cmd, get_output
from subprocess import CalledProcessError

log = logging.getLogger(__name__)

def check_buildbot():
    """check if buildbot command works"""
    try:
        run_cmd(['buildbot', '--version'])
    except CalledProcessError:
        log.error("FAIL: buildbot command doesn't work", exc_info=True)
        raise


def find_version(contents, versionNumber):
    """Given an open readable file-handle look for the occurrence
       of the version # in the file"""
    ret = re.search(re.compile(re.escape(versionNumber), re.DOTALL), contents)
    return ret


def locale_diff(locales1, locales2):
    """ accepts two lists and diffs them both ways, returns any differences
    found """
    diff_list = [locale for locale in locales1 if not locale in locales2]
    diff_list.extend(locale for locale in locales2 if not locale in locales1)
    return diff_list


def get_buildbot_username_param():
    cmd = ['buildbot', 'sendchange', '--help']
    output = get_output(cmd)
    if "-W, --who=" in output:
        return "--who"
    else:
        return "--username"


def sendchange(branch, revision, username, master, products):
    """Send the change to buildbot to kick off the release automation"""
    if isinstance(products, basestring):
        products = [products]
    cmd = [
        'buildbot',
        'sendchange',
        get_buildbot_username_param(),
        username,
        '--master',
        master,
        '--branch',
        branch,
        '-p',
        'products:%s' % ','.join(products),
        '-p',
        'script_repo_revision:%s' % revision,
        'release_build'
    ]
    logging.info("Executing: %s" % cmd)
    run_cmd(cmd)
