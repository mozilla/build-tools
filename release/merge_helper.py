#!/usr/bin/python
"""A merge day helper script to go along with
https://wiki.mozilla.org/Release_Management/Merge_Documentation"""
# lint_ignore=E501,C901

import logging
import argparse
import site
from os import path

log = logging.getLogger(__name__)
site.addsitedir(path.join(path.dirname(__file__), "../lib/python"))
from beta2release import replace, strip_outgoing
from util.commands import run_cmd
from util.hg import (mercurial, update, tag, get_revision, pull,
                     merge_via_debugsetparents, commit)

mc_dir = "mozilla-central"
ma_dir = "mozilla-aurora"
mb_dir = "mozilla-beta"
mc_repo = "ssh://hg.mozilla.org/mozilla-central"
ma_repo = "ssh://hg.mozilla.org/releases/mozilla-aurora"
mb_repo = "ssh://hg.mozilla.org/releases/mozilla-beta"

branding_dirs = ["mobile/android/config/mozconfigs/android",
                 "mobile/android/config/mozconfigs/android-armv6",
                 "mobile/android/config/mozconfigs/android-x86"]
branding_files = ["debug", "l10n-nightly", "nightly"]

profiling_files = ["mobile/android/config/mozconfigs/android/nightly",
                   "browser/config/mozconfigs/linux32/nightly",
                   "browser/config/mozconfigs/linux64/nightly",
                   "browser/config/mozconfigs/macosx-universal/nightly",
                   "browser/config/mozconfigs/win32/nightly",
                   "browser/config/mozconfigs/win64/nightly"]
elf_hack_files = ["mobile/android/config/mozconfigs/android/nightly",
                  "browser/config/mozconfigs/linux32/nightly",
                  "browser/config/mozconfigs/linux64/nightly"]


def get_major_version(d):
    with open(path.join(d, "browser/config/version.txt")) as f:
        version = f.readline().split(".")[0]
    return version


def bump_version(d, curr_version, next_version, curr_suffix, next_suffix,
                 bump_major=False):
    curr_weave_version = str(int(curr_version) + 2)
    next_weave_version = str(int(curr_weave_version) + 1)
    version_files = ["browser/config/version.txt", "config/milestone.txt",
                     "mobile/android/confvars.sh", "b2g/confvars.sh"]
    for f in version_files:
        replace(path.join(d, f), "%s.0%s" % (curr_version, curr_suffix),
                "%s.0%s" % (next_version, next_suffix))
    # only applicable for m-c
    if bump_major:
        replace(path.join(d, "xpcom/components/Module.h"),
                "static const unsigned int kVersion = %s;" % curr_version,
                "static const unsigned int kVersion = %s;" % next_version)
        replace(path.join(d, "services/sync/Makefile.in"),
                "weave_version := 1.%s.0" % curr_weave_version,
                "weave_version := 1.%s.0" % next_weave_version)


def main():
    logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--hg-user", default="ffxbld <release@mozilla.com>",
                        help="Mercurial username to be passed to hg -u")

    args = parser.parse_args()
    hg_user = args.hg_user

    # prep the repos
    for d, repo in ((mc_dir, mc_repo), (ma_dir, ma_repo), (mb_dir, mb_repo)):
        mercurial(repo, d)
        log.info("Cleaning up %s...", d)
        strip_outgoing(d)
        update(d, branch="default")

    curr_mc_version = get_major_version(mc_dir)
    curr_ma_version = get_major_version(ma_dir)
    curr_mb_version = get_major_version(mb_dir)

    next_mc_version = str(int(curr_mc_version) + 1)
    next_ma_version = str(int(curr_ma_version) + 1)
    next_mb_version = str(int(curr_mb_version) + 1)

    # mozilla-central
    mc_revision = get_revision(mc_dir)
    mc_tag = "FIREFOX_AURORA_%s_BASE" % curr_mc_version
    tag(mc_dir, tags=[mc_tag], rev=mc_revision, user=hg_user,
        msg="Added %s tag for changeset %s. IGNORE BROKEN CHANGESETS  DONTBUILD CLOSED TREE NO BUG a=release" %
        (mc_tag, mc_revision))
    new_mc_revision = get_revision(mc_dir)
    bump_version(mc_dir, curr_mc_version, next_mc_version, "a1", "a1",
                 bump_major=True)

    raw_input("Hit 'return' to display diffs onscreen")
    run_cmd(["hg", "diff"], cwd=mc_dir)
    raw_input("If the diff looks good hit return to commit those changes")
    commit(mc_dir, user=hg_user,
           msg="Version bump. IGNORE BROKEN CHANGESETS CLOSED TREE NO BUG a=release")
    raw_input("Go ahead and push mozilla-central...and continue to "
              "mozilla-aurora to mozilla-beta uplift ")

    # mozilla-aurora
    ma_revision = get_revision(ma_dir)
    ma_tag = "FIREFOX_BETA_%s_BASE" % curr_ma_version
    ma_end_tag = "FIREFOX_AURORA_%s_END" % curr_ma_version
    # pull must use revision not tag
    pull(mc_dir, dest=ma_dir, revision=new_mc_revision)
    merge_via_debugsetparents(
        ma_dir, old_head=ma_revision, new_head=new_mc_revision,
        user=hg_user, msg="Merge old head via |hg debugsetparents %s %s|. "
        "CLOSED TREE DONTBUILD a=release" % (new_mc_revision, ma_revision))
    tag(ma_dir, tags=[ma_tag, ma_end_tag], rev=ma_revision, user=hg_user,
        msg="Added %s %s tags for changeset %s. IGNORE BROKEN CHANGESETS DONTBUILD CLOSED TREE NO BUG a=release" %
        (ma_tag, ma_end_tag,  ma_revision))
    bump_version(ma_dir, next_ma_version, next_ma_version, "a1", "a2")
    raw_input("Hit 'return' to display diffs onscreen")
    run_cmd(["hg", "diff"], cwd=ma_dir)
    raw_input("If the diff looks good hit return to commit those changes")
    commit(ma_dir, user=hg_user, msg="Version bump. IGNORE BROKEN CHANGESETS CLOSED TREE NO BUG a=release")

    replace(path.join(ma_dir, "browser/confvars.sh"),
            "MOZ_BRANDING_DIRECTORY=browser/branding/nightly",
            "MOZ_BRANDING_DIRECTORY=browser/branding/aurora")
    replace(path.join(ma_dir, "browser/confvars.sh"),
            "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-central",
            "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-aurora")
    replace(path.join(ma_dir, "browser/confvars.sh"),
            "MAR_CHANNEL_ID=firefox-mozilla-central",
            "MAR_CHANNEL_ID=firefox-mozilla-aurora")
    for d in branding_dirs:
        for f in branding_files:
            replace(path.join(ma_dir, d, f),
                    "ac_add_options --with-branding=mobile/android/branding/nightly",
                    "ac_add_options --with-branding=mobile/android/branding/aurora")
            if f == "l10n-nightly":
                replace(path.join(ma_dir, d, f),
                        "ac_add_options --with-l10n-base=../../l10n-central",
                        "ac_add_options --with-l10n-base=..")
    for f in profiling_files:
        replace(path.join(ma_dir, f), "ac_add_options --enable-profiling", "")
    for f in elf_hack_files:
        replace(path.join(ma_dir, f),
                "ac_add_options --disable-elf-hack # --enable-elf-hack conflicts with --enable-profiling", "")

    raw_input("Hit 'return' to display diffs onscreen")
    run_cmd(["hg", "diff"], cwd=ma_dir)
    raw_input("If the diff looks good hit return to commit those changes")
    commit(ma_dir, user=hg_user,
           msg="Update configs. IGNORE BROKEN CHANGESETS CLOSED TREE NO BUG a=release ba=release")
    raw_input("Go ahead and push mozilla-aurora changes.")

    # mozilla-beta
    mb_revision = get_revision(mb_dir)
    mb_tag = "FIREFOX_BETA_%s_END" % curr_mb_version
    # pull must use revision not tag
    pull(ma_dir, dest=mb_dir, revision=ma_revision)
    merge_via_debugsetparents(
        mb_dir, old_head=mb_revision, new_head=ma_revision,
        user=hg_user, msg="Merge old head via |hg debugsetparents %s %s|. "
        "CLOSED TREE DONTBUILD a=release" % (ma_revision, mb_revision))
    tag(mb_dir, tags=[mb_tag], rev=mb_revision, user=hg_user,
        msg="Added %s tag for changeset %s. IGNORE BROKEN CHANGESETS DONTBUILD CLOSED TREE NO BUG a=release" %
        (mb_tag, mb_revision))
    bump_version(mb_dir, next_mb_version, next_mb_version, "a2", "")
    raw_input("Hit 'return' to display diffs onscreen")
    run_cmd(["hg", "diff"], cwd=mb_dir)
    raw_input("If the diff looks good hit return to commit those changes")
    commit(mb_dir, user=hg_user, msg="Version bump. IGNORE BROKEN CHANGESETS CLOSED TREE NO BUG a=release")
    replace(path.join(mb_dir, "browser/confvars.sh"),
            "MOZ_BRANDING_DIRECTORY=browser/branding/aurora",
            "MOZ_BRANDING_DIRECTORY=browser/branding/nightly")
    replace(path.join(mb_dir, "browser/confvars.sh"),
            "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-aurora",
            "ACCEPTED_MAR_CHANNEL_IDS=firefox-mozilla-beta,firefox-mozilla-release")
    replace(path.join(mb_dir, "browser/confvars.sh"),
            "MAR_CHANNEL_ID=firefox-mozilla-aurora",
            "MAR_CHANNEL_ID=firefox-mozilla-beta")
    for d in branding_dirs:
        for f in branding_files:
            replace(path.join(mb_dir, d, f),
                    "ac_add_options --with-branding=mobile/android/branding/aurora",
                    "ac_add_options --with-branding=mobile/android/branding/beta")
    raw_input("Hit 'return' to display diffs onscreen")
    run_cmd(["hg", "diff"], cwd=mb_dir)
    raw_input("If the diff looks good hit return to commit those changes")
    commit(mb_dir, user=hg_user,
           msg="Update configs. IGNORE BROKEN CHANGESETS CLOSED TREE NO BUG a=release ba=release")
    raw_input("Go ahead and push mozilla-beta changes.")

if __name__ == "__main__":
    main()
