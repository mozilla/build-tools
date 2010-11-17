"""Functions for interacting with hg"""
import os, re, subprocess
from urlparse import urlsplit

from util.commands import run_cmd, get_output, remove_path

import logging
log = logging.getLogger(__name__)

class DefaultShareBase:
    pass
DefaultShareBase = DefaultShareBase()

def _make_absolute(repo):
    if repo.startswith("file://"):
        path = repo[len("file://"):]
        repo = "file://%s" % os.path.abspath(path)
    elif "://" not in repo:
        repo = os.path.abspath(repo)
    return repo

def make_hg_url(baseurl, branch, revision, filename=None):
    """construct a valid hg url from a base hg url (hg.mozilla.org),
    branch, revision and possible filename"""
    if not filename:
        return '/'.join([p.strip('/') for p in [baseurl, branch, 'rev', revision]])
    else:
        return '/'.join([p.strip('/') for p in [baseurl, branch, 'raw-file', revision, filename]])

def get_repo_path(repo):
     repo = _make_absolute(repo)
     if repo.startswith("/"):
         return repo.lstrip("/")
     else:
         return urlsplit(repo).path.lstrip("/")

def get_revision(path):
    """Returns which revision directory `path` currently has checked out."""
    return get_output(['hg', 'parent', '--template', '{node|short}'], cwd=path)

def hg_ver():
    """Returns the current version of hg, as a tuple of
    (major, minor, build)"""
    ver_string = get_output(['hg', '-q', 'version'])
    match = re.search("\(version ([0-9.]+)\)", ver_string)
    if match:
        bits = match.group(1).split(".")
        if len(bits) < 3:
            bits += (0,)
        ver = tuple(int(b) for b in bits)
    else:
        ver = (0, 0, 0)
    log.debug("Running hg version %s", ver)
    return ver

def update(dest, branch=None, revision=None):
    """Updates working copy `dest` to `branch` or `revision`.  If neither is
    set then the working copy will be updated to the latest revision on the
    current branch.  Local changes will be discarded."""
    # If we have a revision, switch to that
    if revision is not None:
        cmd = ['hg', 'update', '-C', '-r', revision]
        run_cmd(cmd, cwd=dest)
    else:
        # Check & switch branch
        local_branch = get_output(['hg', 'branch'], cwd=dest).strip()

        cmd = ['hg', 'update', '-C']

        # If this is different, checkout the other branch
        if branch and branch != local_branch:
            cmd.append(branch)

        run_cmd(cmd, cwd=dest)
    return get_revision(dest)

def clone(repo, dest, branch=None, revision=None, update_dest=True):
    """Clones hg repo and places it at `dest`, replacing whatever else is
    there.  The working copy will be empty.

    If `revision` is set, only the specified revision and its ancestors will be
    cloned.

    If `update_dest` is set, then `dest` will be updated to `revision` if set,
    otherwise to `branch`, otherwise to the head of default."""
    if os.path.exists(dest):
        remove_path(dest)

    cmd = ['hg', 'clone', '-U']
    if revision:
        cmd.extend(['-r', revision])
    elif branch:
        # hg >= 1.6 supports -b branch for cloning
        ver = hg_ver()
        if ver >= (1, 6, 0):
            cmd.extend(['-b', branch])

    cmd.extend([repo, dest])
    run_cmd(cmd)

    if update_dest:
        return update(dest, branch, revision)

def common_args(revision=None, branch=None, ssh_username=None, ssh_key=None):
    """Fill in common hg arguments, encapsulating logic checks that depend on
       mercurial versions and provided arguments"""
    args = []
    if ssh_username or ssh_key:
        opt = ['-e', 'ssh']
        if ssh_username:
            opt[1] += ' -l %s' % ssh_username
        if ssh_key:
            opt[1] += ' -i %s' % ssh_key
        args.extend(opt)
    if revision:
        args.extend(['-r', revision])
    if branch:
        if hg_ver() >= (1, 6, 0):
            args.extend(['-b', branch])
    return args

def pull(repo, dest, update_dest=True, **kwargs):
    """Pulls changes from hg repo and places it in `dest`.

    If `revision` is set, only the specified revision and its ancestors will be
    pulled.

    If `update_dest` is set, then `dest` will be updated to `revision` if set,
    otherwise to `branch`, otherwise to the head of default.  """
    # Convert repo to an absolute path if it's a local repository
    repo = _make_absolute(repo)
    cmd = ['hg', 'pull']
    cmd.extend(common_args(**kwargs))
    cmd.append(repo)
    run_cmd(cmd, cwd=dest)

    if update_dest:
        branch = None
        if 'branch' in kwargs and kwargs['branch']:
            branch = kwargs['branch']
        revision = None
        if 'revision' in kwargs and kwargs['revision']:
            revision = kwargs['revision']
        return update(dest, branch=branch, revision=revision)

def out(src, remote, **kwargs):
    """Check for outgoing changesets present in a repo"""
    cmd = ['hg', '-q', 'out', '--template', '{node}\n']
    cmd.extend(common_args(**kwargs))
    cmd.append(remote)
    if os.path.exists(src):
        try:
            return get_output(cmd, cwd=src).rstrip().split("\n")
        except subprocess.CalledProcessError, inst:
            if inst.returncode == 1:
                return None
            raise

def mercurial(repo, dest, branch=None, revision=None,
              shareBase=DefaultShareBase):
    """Makes sure that `dest` is has `revision` or `branch` checked out from
    `repo`.

    Do what it takes to make that happen, including possibly clobbering
    dest."""
    dest = os.path.abspath(dest)
    if shareBase is DefaultShareBase:
        shareBase = os.environ.get("HG_SHARE_BASE_DIR", None)

    # If the working directory already exists and isn't using share we update
    # the working directory directly from the repo, ignoring the sharing
    # settings
    if os.path.exists(dest):
        if not os.path.exists(os.path.join(dest, ".hg", "sharedpath")):
            try:
                return pull(repo, dest, branch=branch, revision=revision)
            except subprocess.CalledProcessError:
                log.warning("Error pulling changes into %s from %s; clobbering", dest, repo)
                log.debug("Exception:", exc_info=True)
                remove_path(dest)

    # If that fails for any reason, and sharing is requested, we'll try to
    # update the shared repository, and then update the working directory from
    # that.
    if shareBase:
        sharedRepo = os.path.join(shareBase, get_repo_path(repo))
        try:
            mercurial(repo, sharedRepo, branch=branch, revision=revision,
                      shareBase=None)
            if os.path.exists(dest):
                return update(dest, branch=branch, revision=revision)
            else:
                return share(sharedRepo, dest, branch=branch, revision=revision)
        except subprocess.CalledProcessError:
            log.warning("Error updating %s from sharedRepo (%s): ", dest, sharedRepo)
            log.debug("Exception:", exc_info=True)
            remove_path(dest)

    if not os.path.exists(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))
    # Share isn't available or has failed, clone directly from the source
    return clone(repo, dest, branch, revision)

def share(source, dest, branch=None, revision=None):
    """Creates a new working directory in "dest" that shares history with
       "source" using Mercurial's share extension"""
    run_cmd(['hg', 'share', source, dest])
    return update(dest, branch=branch, revision=revision)
