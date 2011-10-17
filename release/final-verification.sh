#!/bin/bash

if [ $# -lt 1 ]; then
    echo "Usage: $0 [list of update verify configs]"
    exit 1
fi

configs="$@"

cd updates
cat $configs | sed 's/betatest/releasetest/' > update.cfg
./verify.sh -t update.cfg 2>&1 | tee quickVerify.log
# this command's exit status will be 1 regardless of whether it passed or failed
# we grep the log so we can inform buildbot correctly
if grep HTTP/ quickVerify.log | grep -v 200 | grep -qv 302; then
    # One or more links failed
    exit 1
elif grep '^FAIL' quickVerify.log; then
    # Usually this means that we got an empty update.xml
    exit 1
else
    # Everything passed
    exit 0
fi
