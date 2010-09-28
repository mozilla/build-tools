"""Functions for interacting with hg"""
import os, re, subprocess

from util.commands import run_cmd, get_output, remove_path

import logging
log = logging.getLogger(__name__)

def _make_absolute(repo):
    if repo.startswith("file://"):
        path = repo[len("file://"):]
        repo = "file://%s" % os.path.abspath(path)
    elif "://" not in repo:
        repo = os.path.abspath(repo)
    return repo

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

def pull(repo, dest, branch=None, revision=None, update_dest=True):
    """Pulls changes from hg repo and places it in `dest`.

    If `revision` is set, only the specified revision and its ancestors will be
    pulled.

    If `update_dest` is set, then `dest` will be updated to `revision` if set,
    otherwise to `branch`, otherwise to the head of default.  """
    # Convert repo to an absolute path if it's a local repository
    repo = _make_absolute(repo)
    cmd = ['hg', 'pull']
    if revision is not None:
        cmd.extend(['-r', revision])
    elif branch:
        # hg >= 1.6 supports -b branch for cloning
        if hg_ver() >= (1, 6, 0):
            cmd.extend(['-b', branch])
    cmd.append(repo)
    run_cmd(cmd, cwd=dest)

    if update_dest:
        return update(dest, branch, revision)

def mercurial(repo, dest, branch=None, revision=None):
    """Makes sure that `dest` is has `revision` or `branch` checked out from
    `repo`.

    Do what it takes to make that happen, including possibly clobbering
    dest."""

    # If dest exists, try pulling first
    log.debug("mercurial: %s %s", repo, dest)
    if os.path.exists(dest):
        log.debug("%s exists, pulling", dest)
        try:
            # TODO: If revision is set, try updating before pulling?
            return pull(repo, dest, branch, revision)
        except subprocess.CalledProcessError:
            log.warning("Error pulling changes into %s from %s; clobbering", dest,
                    repo)
            log.debug("Exception:", exc_info=True)
            remove_path(dest)

    # If it doesn't exist, clone it!
    return clone(repo, dest, branch, revision)
