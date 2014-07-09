#!/bin/bash

VENV=$1
LOGFILE=$2
CONFIG=$3

if [ -z "$VENV" ]; then
    VENV=/home/cltbld/release-runner/venv
fi

if [ ! -e "$VENV" ]; then
    echo "Could not find Python virtual environment '$VENV'"
    exit 1
fi

if [ -z "$LOGFILE" ]; then
    LOGFILE=/var/log/supervisor/release-runner.log
fi

LOGFILE_DIR=$(dirname $LOGFILE)
if [ ! -e $LOGFILE_DIR  ]; then
    echo "Could not find directory '$LOGFILE_DIR' for the logs"
    exit 1
fi

if [ -z "$CONFIG" ]; then
    CONFIG=/home/cltbld/.release-runner.ini
fi

if [ ! -e "$CONFIG" ]; then
    echo "Could not find configuration file '$CONFIG'"
    exit 1
fi

# Mozilla hg is symlinked as /usr/local/bin/hg
export PATH=/usr/local/bin:$PATH

. $VENV/bin/activate

# Sleep time after a failure, in seconds.
SLEEP_TIME=60
NOTIFY_TO=$(grep "notify_to:" $CONFIG|sed -e "s|.*<\(.*\)>|\1|g")
if [ -z "$NOTIFY_TO" ]; then
    NOTIFY_TO="release@mozilla.com"
fi


CURR_DIR=$(cd $(dirname $0); pwd)
HOSTNAME=`hostname -s`

cd $CURR_DIR

python release-runner.py -c $CONFIG
RETVAL=$?
# Exit code 5 is a failure during polling. We don't want to send mail about
# this, because it will just try again after sleeping.
if [[ $RETVAL == 5 ]]; then
    sleep $SLEEP_TIME;
# Any other non-zero exit code is some other issue, and we should send mail
# about it.
elif [[ $RETVAL != 0 ]]; then
    (
        echo "Release runner encountered a runtime error: "
        tail -n20 $LOGFILE
        echo
        echo "The full log is available on $HOSTNAME in $LOGFILE"
        echo "I'll sleep for $SLEEP_TIME seconds before retry"
        echo
        echo "- release runner"
    ) | mail -s "[release-runner] failed" $NOTIFY_TO

    sleep $SLEEP_TIME
fi
