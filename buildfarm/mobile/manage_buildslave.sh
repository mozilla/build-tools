#!/bin/bash
PWD=`pwd`
DEVICE=`basename $PWD`
opt="$1"
BB_PATH=/tools/buildbot-0.8.4-pre-moz2/bin/buildslave
BB_PYTHON=/tools/buildbot-0.8.4-pre-moz2/bin/python2.7
BB_TWISTD=/tools/buildbot-0.8.4-pre-moz2/bin/twistd

if [ -z $1 ]; then
    echo You can call this script with *gettac* or all other options that buildslave can take
    ${BB_PATH} --help
    exit 1
fi

if [ "$opt" = "gettac" ]; then
    rm buildbot.tac
    wget -q -O/builds/$DEVICE/buildbot.tac http://slavealloc.build.mozilla.org/gettac/$DEVICE
elif [ "$opt" = "start" ]; then
    echo "We want to always start buildbot through twistd"
    echo "We will run with the twistd command instead of calling buildslave"
    ${BB_PYTHON} ${BB_TWISTD} --no_save \
        --rundir=/builds/$DEVICE \
        --pidfile=/builds/$DEVICE/twistd.pid \
        --python=/builds/$DEVICE/buildbot.tac
    tail /builds/$DEVICE/twistd.log
else
    ${BB_PATH} $opt
fi
