#!/bin/bash

if [ $# -lt 2 ]; then
    echo "Usage: $0 cvsroot [list of update verify configs]"
    exit 1
fi

cvsroot=$1
shift
configs="$@"

cvs -d$cvsroot checkout -d updates mozilla/testing/release/updates
if [ $? != 0 ]; then
    echo "Could not checkout mozilla/testing/release/updates"
    exit 1
fi
cvs -d$cvsroot checkout -d common mozilla/testing/release/common
if [ $? != 0 ]; then
    echo "Could not checkout mozilla/testing/release/common"
    exit 1
fi

cd updates
cat $configs | grep -v major | sed 's/betatest/releasetest/' > update.cfg
./verify.sh -t update.cfg 2>&1 | tee quickVerify.log
# this command's exit status will be 1 regardless of whether it passed or failed
# we grep the log so we can inform buildbot correctly
if grep HTTP quickVerify.log | grep -v 200 | grep -qv 302; then
    # One or more links failed
    exit 1
else
    # Everything passed
    exit 0
fi
