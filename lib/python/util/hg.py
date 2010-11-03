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

def make_hg_url(baseurl, branch, revision, filename=None):
    """construct a valid hg url from a base hg url (hg.mozilla.org),
    branch, revision and possible filename"""
    if not filename:
        return '/'.join([p.strip('/') for p in [baseurl, branch, 'rev', revision]])
    else:
        return '/'.join([p.strip('/') for p in [baseurl, branch, 'raw-file', revision, filename]])

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
            return pull(repo, dest, branch=branch, revision=revision)
        except subprocess.CalledProcessError:
            log.warning("Error pulling changes into %s from %s; clobbering", dest,
                    repo)
            log.debug("Exception:", exc_info=True)
            remove_path(dest)

    # If it doesn't exist, clone it!
    return clone(repo, dest, branch, revision)

def share(source, dest, branch=None, revision=None):
    """Uses the hg share extension to update a working dir from a shared repo
    """
    if os.path.exists(os.path.join(dest, ".hg", "sharedpath")):
        log.debug("path exists, just going to update")
        #attempt to update from the shared history. If this fails
        try:
            return update(dest, branch, revision)
        except subprocess.CalledProcessError:
            remove_path(dest)
    log.debug("sharing hg repo to %s" % dest)
    #fall back to creating a local clone if the share extension is unavailable
    #or if share fails for any other reason
    try:
        cmd = ['hg', 'share', source, dest]
        run_cmd(cmd)
        return update(dest, branch, revision)
    #if it fails for whatever reason, use mercurial() to force a local clone
    except subprocess.CalledProcessError:
        log.error("Failed to hg_share on hg version %s, attemping local clone" % (hg_ver(),))
        return mercurial(source, dest, branch, revision)
