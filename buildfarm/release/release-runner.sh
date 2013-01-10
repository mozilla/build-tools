#!/bin/bash

# XXX: TODO: remove the following hack
. /home/cltbld/release-runner/venv/bin/activate

# Sleep 3 days in case of failure
SLEEP_TIME=259200
NOTIFY_TO=release@mozilla.com
CONFIG=/home/cltbld/.release-runner.ini

CURR_DIR=$(cd $(dirname $0); pwd)
HOSTNAME=`hostname -s`

cd $CURR_DIR

python release-runner.py -c $CONFIG
RETVAL=$?
if [[ $RETVAL != 0 ]]; then
    (
        echo "Release runner encountered a runtime error"
        echo
        echo "Please check the output log on $HOSTNAME"
        echo "I'll sleep for $SLEEP_TIME seconds before retry"
        echo
        echo "- release runner"
    ) | mail -s "[release-runner] failed at $HOSTNAME" $NOTIFY_TO

    sleep $SLEEP_TIME
fi
