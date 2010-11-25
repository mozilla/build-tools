#!/bin/bash

# 2010-09-10 - compare downloaded single files before cloning (ccooper)
# 2008-06-27 - Copied from sync-blocklist (dtownsend)
# 2008-07-14 - Use a permanent local clone (dtownsend)
# 2008-07-24 - Fix hg username (dtownsend)

USAGE="usage: $0 [-n] [-c] [-d] [-u hg_ssh_user] [-k hg_ssh_key] -b branch"
DRY_RUN=false
BRANCH=""
CLOSED_TREE=false
DONTBUILD=false
HG_SSH_USER='ffxbld'
HG_SSH_KEY='~cltbld/.ssh/ffxbld_dsa'
while [ $# -gt 0 ]; do
    case "$1" in
        -b) BRANCH="$2"; shift;;
        -n) DRY_RUN=true;;
        -c) CLOSED_TREE=true;;
        -d) DONTBUILD=true;;
        -u) HG_SSH_USER="$2"; shift;;
        -k) HG_SSH_KEY="$2"; shift;;
        -*) echo >&2 \
	    $USAGE
            exit 1;;
        *)  break;; # terminate while loop
    esac
    shift
done

if [ "$BRANCH" == "" ]; then
    echo >&2 $USAGE
    exit 1
fi

HGHOST="hg.mozilla.org"
HGREPO="http://${HGHOST}/${BRANCH}"
HGPUSHREPO="ssh://${HGHOST}/${BRANCH}"
BLOCKLIST_URL_HG="${HGREPO}/raw-file/default/browser/app/blocklist.xml"
REPODIR='blocklist'

HG=hg
WGET=wget
DIFF=diff
HOST=`/bin/hostname -s`

compare_blocklists()
{
    VERSION_URL_HG="${HGREPO}/raw-file/default/browser/config/version.txt"
    rm -f version.txt
    ${WGET} --no-check-certificate -O version.txt ${VERSION_URL_HG}
    WGET_STATUS=$?
    if [ $WGET_STATUS != 0 ]; then
        echo "ERROR wget exited with a non-zero exit code: $WGET_STATUS"
        return $WGET_STATUS
    fi
    VERSION=`cat version.txt | sed 's/[^.0-9]*$//'`
    if [ "$VERSION" == "" ]; then
        echo "ERROR Unable to parse version from version.txt"
    fi     

    BLOCKLIST_URL_AMO="https://addons.mozilla.org/blocklist/3/%7Bec8030f7-c20a-464f-9b0e-13a3a9e97384%7D/${VERSION}/Firefox/20090105024647/blocklist-sync/en-US/nightly/blocklist-sync/default/default/"
    rm -f blocklist_amo.xml
    ${WGET} --no-check-certificate -O blocklist_amo.xml ${BLOCKLIST_URL_AMO}
    WGET_STATUS=$?
    if [ $WGET_STATUS != 0 ]; then
        echo "ERROR wget exited with a non-zero exit code: $WGET_STATUS"
        return $WGET_STATUS
    fi

    rm -f blocklist_hg.xml
    ${WGET} -O blocklist_hg.xml ${BLOCKLIST_URL_HG}
    WGET_STATUS=$?
    if [ $WGET_STATUS != 0 ]; then
        echo "ERROR wget exited with a non-zero exit code: $WGET_STATUS"
        return $WGET_STATUS
    fi

    ${DIFF} blocklist_hg.xml blocklist_amo.xml >/dev/null 2>&1
    DIFF_STATUS=$?
    case "$DIFF_STATUS" in
        0|1) ;;
        *) echo "ERROR diff exited with exit code: $DIFF_STATUS"
           exit $DIFF_STATUS
    esac
    return $DIFF_STATUS
}

update_blocklist_in_hg()
{
    if [ ! -d $REPODIR ]; then
	echo ${HG} clone $HGREPO $REPODIR
        ${HG} clone $HGREPO $REPODIR
        CLONE_STATUS=$?
        if [ $CLONE_STATUS != 0 ]; then
            echo "ERROR hg clone exited with a non-zero exit code: $CLONE_STATUS"
            return $CLONE_STATUS
        fi
    fi

    echo ${HG} -R $REPODIR pull
    ${HG} -R $REPODIR pull
    PULL_STATUS=$?
    if [ $PULL_STATUS != 0 ]; then
        echo "ERROR hg pull exited with a non-zero exit code: $PULL_STATUS"
        return $PULL_STATUS
    fi
    echo ${HG} -R $REPODIR update -C default
    ${HG} -R $REPODIR update -C default
    UPDATE_STATUS=$?
    if [ $UPDATE_STATUS != 0 ]; then
        echo "ERROR hg update exited with a non-zero exit code: $PULL_STATUS"
        return $UPDATE_STATUS
    fi

    cp -f blocklist_amo.xml ${REPODIR}/browser/app/blocklist.xml
    COMMIT_MESSAGE="Automated blocklist update from host $HOST"
    if [ $DONTBUILD == true ]; then
        COMMIT_MESSAGE="${COMMIT_MESSAGE} (DONTBUILD)"
    fi
    if [ $CLOSED_TREE == true ]; then
        COMMIT_MESSAGE="${COMMIT_MESSAGE} - CLOSED TREE a=blocklist-update"
    fi
    echo ${HG} -R $REPODIR commit -u "${HG_SSH_USER}" -m "${COMMIT_MESSAGE}"
    ${HG} -R $REPODIR commit -u "${HG_SSH_USER}" -m "${COMMIT_MESSAGE}"
    echo ${HG} -R $REPODIR push -e "ssh -l ${HG_SSH_USER} -i ${HG_SSH_KEY}" ${HGPUSHREPO}
    ${HG} -R $REPODIR push -e "ssh -l ${HG_SSH_USER} -i ${HG_SSH_KEY}" ${HGPUSHREPO}
    PUSH_STATUS=$?
    if [ $PUSH_STATUS != 0 ]; then
        echo "ERROR hg push exited with exit code: $PUSH_STATUS, probably raced another changeset"
        echo ${HG} -R $REPODIR rollback
        ${HG} -R $REPODIR rollback
        ROLLBACK_STATUS=$?
        if [ $ROLLBACK_STATUS != 0 ]; then
            echo "ERROR hg rollback failed with exit code: $ROLLBACK_STATUS"
            echo "This is unrecoverable, removing the local clone to start fresh next time."
            rm -rf $REPODIR
            return $ROLLBACK_STATUS
        fi
    fi
    return $PUSH_STATUS
}

compare_blocklists
result=$?
if [ $result != 0 ]; then
    if [ "$DRY_RUN" == "true" ]; then
        echo "Blocklist files differ, but not updating hg in dry-run mode."
    else   
        echo "Blocklist files differ, updating hg."
        update_blocklist_in_hg
        result=$?
    fi
else
    echo "Blocklist files are identical. Nothing to update."
fi
exit $result
