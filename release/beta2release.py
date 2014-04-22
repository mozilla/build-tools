#!/usr/bin/env python
"""A merge day helper script for Beta-->Release migration to go along with
https://wiki.mozilla.org/Release_Management/Merge_Documentation"""
# lint_ignore=E501

import site
import datetime
import logging
import argparse
import shutil
from os import path
from tempfile import mkstemp

log = logging.getLogger(__name__)
site.addsitedir(path.join(path.dirname(__file__), "../lib/python"))

from util.retry import retrying
from util.commands import run_cmd
from util.hg import (mercurial, update, tag, get_revision, pull,
                     merge_via_debugsetparents, commit)

branding_dirs = ["mobile/android/config/mozconfigs/android/",
                 "mobile/android/config/mozconfigs/android-armv6/",
                 "mobile/android/config/mozconfigs/android-x86/"]
branding_files = ["release", "l10n-release", "l10n-nightly", "nightly"]


def replace(file_name, from_, to_):
    text = open(file_name).read()
    new_text = text.replace(from_, to_)
    if text == new_text:
        raise RuntimeError(
            "Cannot replace '%s' to '%s' in '%s'" %
            (from_, to_, file_name))

    _, tmp_file_path = mkstemp()
    with open(tmp_file_path, "w") as out:
        out.write(new_text)
    shutil.move(tmp_file_path, file_name)


def strip_outgoing(dest):
    try:
        run_cmd(["hg", "strip", "--no-backup", "outgoing()"], cwd=dest)
    except Exception:
        log.warn("Ignoring strip error in %s", dest)


def remove_locales(file_name, locales):
    _, tmp_file_path = mkstemp()
    with open(file_name) as f:
        lines = f.readlines()
    with open(tmp_file_path, "w") as out:
        for line in lines:
            locale = line.split()[0]
            if locale not in locales:
                out.write(line)
            else:
                log.warn("Removied locale: %s", locale)
    shutil.move(tmp_file_path, file_name)


def main():
    logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-dir", default="mozilla-beta",
                        help="Working directory of repo to be merged from")
    parser.add_argument("--from-repo",
                        default="ssh://hg.mozilla.org/releases/mozilla-beta",
                        help="Repo to be merged from")
    parser.add_argument("--to-dir", default="mozilla-release",
                        help="Working directory of repo to be merged to")
    parser.add_argument(
        "--to-repo", default="ssh://hg.mozilla.org/releases/mozilla-release",
        help="Repo to be merged to")
    parser.add_argument("--hg-user", default="ffxbld <release@mozilla.com>",
                        help="Mercurial username to be passed to hg -u")
    parser.add_argument("--remove-locale", dest="remove_locales", action="append",
                        required=True,
                        help="Locales to be removed from release shipped-locales")

    args = parser.parse_args()
    from_dir = args.from_dir
    to_dir = args.to_dir
    from_repo = args.from_repo
    to_repo = args.to_repo
    hg_user = args.hg_user

    with retrying(mercurial) as clone:
        for (d, repo) in ((from_dir, from_repo), (to_dir, to_repo)):
            clone(repo, d)
            log.info("Cleaning up %s...", d)
            strip_outgoing(d)
            update(d, branch="default")
    beta_rev = get_revision(from_dir)
    release_rev = get_revision(to_dir)

    now = datetime.datetime.now()
    date = now.strftime("%Y%m%d")
    # TODO: make this tag consistent with other branches
    release_base_tag = "RELEASE_BASE_" + date

    log.info("Tagging %s beta with %s", beta_rev, release_base_tag)
    tag(from_dir, tags=[release_base_tag], rev=beta_rev, user=hg_user,
        msg="Added %s tag for changeset %s. DONTBUILD CLOSED TREE a=release" %
        (release_base_tag, beta_rev))
    new_beta_rev = get_revision(from_dir)
    raw_input("Push mozilla-beta and hit Return")

    pull(from_dir, dest=to_dir)
    merge_via_debugsetparents(
        to_dir, old_head=release_rev, new_head=new_beta_rev, user=hg_user,
        msg="Merge old head via |hg debugsetparents %s %s|. "
        "CLOSED TREE DONTBUILD a=release" % (new_beta_rev, release_rev))

    replace(
        path.join(to_dir, "browser/confvars.sh"),
        "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-beta,firefox-mozilla-release",
        "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-release")
    replace(path.join(to_dir, "browser/confvars.sh"),
            "MAR_CHANNEL_ID=firefox-mozilla-beta",
            "MAR_CHANNEL_ID=firefox-mozilla-release")

    for d in branding_dirs:
        for f in branding_files:
            replace(
                path.join(to_dir, d, f),
                "ac_add_options --with-branding=mobile/android/branding/beta",
                "ac_add_options --with-branding=mobile/android/branding/official")

    if args.remove_locales:
        log.info("Removing locales: %s", args.remove_locales)
        remove_locales(path.join(to_dir, "browser/locales/shipped-locales"),
                       args.remove_locales)

    log.warn("Apply any manual changes, such as disabling features.")
    raw_input("Hit 'return' to display channel, branding, and feature diffs onscreen")
    run_cmd(["hg", "diff"], cwd=to_dir)
    raw_input("If the diff looks good hit return to commit those changes")
    commit(to_dir, user=hg_user,
           msg="Update configs. CLOSED TREE a=release ba=release")
    raw_input("Go ahead and push mozilla-release changes.")

if __name__ == "__main__":
    main()
