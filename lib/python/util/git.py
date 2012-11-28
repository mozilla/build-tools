"""Functions for interacting with hg"""
import os
import subprocess
import hashlib

from util.commands import run_cmd, get_output, remove_path
from util.file import safe_unlink

import logging
log = logging.getLogger(__name__)


class DefaultShareBase:
    pass
DefaultShareBase = DefaultShareBase()


def _make_absolute(repo):
    if repo.startswith("file://"):
        # Make file:// urls absolute
        path = repo[len("file://"):]
        repo = "file://%s" % os.path.abspath(path)
    elif "://" not in repo:
        repo = os.path.abspath(repo)
    return repo


def has_revision(dest, revision):
    """Returns True if revision exists in dest"""
    try:
        get_output(['git', 'log', '--oneline', '--quiet', revision], cwd=dest, include_stderr=True)
        return True
    except subprocess.CalledProcessError:
        return False


def has_ref(dest, refname):
    """Returns True if refname exists in dest.
    refname can be a branch or tag name."""
    try:
        get_output(['git', 'show-ref', '-d', refname], cwd=dest, include_stderr=True)
        return True
    except subprocess.CalledProcessError:
        return False


def init(dest):
    """Initializes an empty repository at dest. If dest exists, it will be removed."""
    safe_unlink(dest)
    run_cmd(['git', 'init', '-q', dest])


def git(repo, dest, branch=None, revision=None, update_dest=True,
        shareBase=DefaultShareBase, mirrors=None):
    """Makes sure that `dest` is has `revision` or `branch` checked out from
    `repo`.

    Do what it takes to make that happen, including possibly clobbering
    dest.

    If `mirrors` is set, will try and use the mirrors before `repo`.
    """

    if shareBase is DefaultShareBase:
        shareBase = os.environ.get("GIT_SHARE_BASE_DIR", None)

    dest = os.path.abspath(dest)
    repo_hash = hashlib.md5(repo).hexdigest()

    # TODO: Touch something in shareBase/$repo_hash so we know which remotes
    # are being used

    # Update an existing working copy if we've already got one
    if os.path.exists(dest):
        if not os.path.exists(os.path.join(dest, ".git")):
            log.warning("%s doesn't appear to be a valid git directory; clobbering", dest)
            remove_path(dest)
        else:
            try:
                # If we're supposed to be updating to a revision, check if we
                # have that revision already. If so, then there's no need to
                # fetch anything.
                do_fetch = False
                if revision is None:
                    # we don't have a revision specified, so pull in everything
                    do_fetch = True
                elif has_ref(dest, revision):
                    # revision is actually a ref name, so we need to run fetch
                    # to make sure we update the ref
                    do_fetch = True
                elif not has_revision(dest, revision):
                    # we don't have this revision, so need to fetch it
                    do_fetch = True

                if do_fetch:
                    fetch(repo, dest, mirrors=mirrors, branch=branch)
                    if shareBase:
                        # If we're using a share, fetch new refs into the share too
                        # Don't fetch tags
                        fetch(repo, shareBase, mirrors=mirrors, branch=branch,
                              remote_name=repo_hash, fetch_tags=False)
                # can purge old remotes later
                if update_dest:
                    return update(dest, branch=branch, revision=revision)
                return
            except subprocess.CalledProcessError:
                log.warning("Error fetching changes into %s from %s; clobbering", dest, repo)
                log.debug("Exception:", exc_info=True)
                remove_path(dest)

    if not os.path.exists(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))

    if shareBase is not None:
        # Clone into our shared repo
        log.info("Updating our share")
        if not os.path.exists(shareBase):
            os.makedirs(shareBase)

        if not os.path.exists(os.path.join(shareBase, ".git")):
            init(shareBase)
        fetch(repo, shareBase, branch=branch, mirrors=mirrors, remote_name=repo_hash, fetch_tags=False)

        log.info("Doing local clone")
        clone(shareBase, dest, update_dest=False, shared=True)
        # Fix up our remote name
        run_cmd(["git", "remote", "set-url", "origin", repo], cwd=dest)
        # Now fetch new refs
        fetch(repo, dest, branch=branch)
    else:
        clone(repo, dest, branch=branch, update_dest=update_dest, mirrors=mirrors)

    if update_dest:
        log.info("Updating local copy")
        return update(dest, branch=branch, revision=revision)


def clone(repo, dest, branch=None, mirrors=None, shared=False, update_dest=True):
    """Clones git repo and places it at `dest`, replacing whatever else is
    there.  The working copy will be empty.

    If `mirrors` is set, will try and clone from the mirrors before
    cloning from `repo`.

    If `shared` is True, then git shared repos will be used

    If `update_dest` is False, then no working copy will be created
    """
    if os.path.exists(dest):
        remove_path(dest)

    if mirrors:
        log.info("Attempting to clone from mirrors")
        for mirror in mirrors:
            log.info("Cloning from %s", mirror)
            try:
                retval = clone(mirror, dest, branch, update_dest=update_dest)
                return retval
            except KeyboardInterrupt:
                raise
            except:
                log.exception("Problem cloning from mirror %s", mirror)
                continue
        else:
            log.info("Pulling from mirrors failed; falling back to %s", repo)

    cmd = ['git', 'clone', '-q']
    if not update_dest:
        # TODO: Use --bare/--mirror here?
        cmd.append('--no-checkout')

    if shared:
        cmd.append('--shared')

    if branch:
        cmd.extend(['-b', branch])

    cmd.extend([repo, dest])
    run_cmd(cmd)
    if update_dest:
        return get_revision(dest)


def update(dest, branch=None, revision=None, remote_name="origin"):
    """Updates working copy `dest` to `branch` or `revision`.  If neither is
    set then the working copy will be updated to the latest revision on the
    current branch.  Local changes will be discarded."""
    # If we have a revision, switch to that
    if revision is not None:
        cmd = ['git', 'checkout', '-q', '--detach', '-f', revision]
        run_cmd(cmd, cwd=dest)
    else:
        if not branch:
            branch = '%s/master' % remote_name
        else:
            branch = '%s/%s' % (remote_name, branch)
        cmd = ['git', 'checkout', '-q', '--detach', '-f', branch]

        run_cmd(cmd, cwd=dest)
    return get_revision(dest)


def fetch(repo, dest, branch=None, remote_name="origin", mirrors=None, fetch_tags=True):
    """Fetches changes from git repo and places it in `dest`.

    If `mirrors` is set, will try and fetch from the mirrors first before
    `repo`."""

    if mirrors:
        for mirror in mirrors:
            try:
                return fetch(mirror, dest, branch=branch)
            except KeyboardInterrupt:
                raise
            except:
                log.exception("Problem fetching from mirror %s", mirror)
                continue
        else:
            log.info("Pulling from mirrors failed; falling back to %s", repo)

    # Convert repo to an absolute path if it's a local repository
    repo = _make_absolute(repo)
    cmd = ['git', 'fetch', '-q', repo]
    if not fetch_tags:
        # Don't fetch tags into our local tags/ refs since we have no way to
        # associate those with this remote and can't purge it later.
        # Instead, put remote tag refs into remotes/<remote>/tags
        cmd.append('--no-tags')
        cmd.append("+refs/tags/*:refs/remotes/{remote_name}/tags/*".format(remote_name=remote_name))

    if branch:
        cmd.append("+refs/heads/{branch}:refs/remotes/{remote_name}/{branch}".format(branch=branch, remote_name=remote_name))
    else:
        cmd.append("+refs/heads/*:refs/remotes/{remote_name}/*".format(branch=branch, remote_name=remote_name))

    run_cmd(cmd, cwd=dest)


def get_revision(path):
    """Returns which revision directory `path` currently has checked out."""
    return get_output(['git', 'rev-parse', 'HEAD'], cwd=path).strip()
