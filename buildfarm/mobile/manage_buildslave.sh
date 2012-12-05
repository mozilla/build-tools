#!/bin/bash
BB_PATH=/tools/buildbot/bin/buildslave
BB_PYTHON=/tools/buildbot/bin/python2.7
BB_TWISTD=/tools/buildbot/bin/twistd
OPTIONS="gettac start stop restart"

opt="$1"

if [ -z $opt ]; then
    echo "You can call this script with the following options:"
    echo $OPTIONS
    exit 1
else
    if [ -z $2 ]; then
        echo You have to specify which device to manage.
        exit 1
    fi
    DEVICE=$2
    DEVICE_PATH=/builds/${DEVICE}
    if [ ! -d "$DEVICE_PATH" ]; then
        echo "$DEVICE_PATH does not exist. Try again with the correct device name."
        exit 1
    fi
fi


if [ "$opt" = "gettac" ]; then
    rm $DEVICE_PATH/buildbot.tac
    wget -q -O$DEVICE_PATH/buildbot.tac http://slavealloc.build.mozilla.org/gettac/$DEVICE
elif [ "$opt" = "stop" ]; then
    ${BB_PATH} stop $DEVICE_PATH
elif [ "$opt" = "restart" ]; then
    ${BB_PATH} stop $DEVICE_PATH
    opt="start"
fi

if [ "$opt" = "start" ]; then
    echo "We want to always start buildbot through twistd"
    echo "We will run with the twistd command instead of calling buildslave"
    pushd $DEVICE_PATH
    ${BB_PYTHON} ${BB_TWISTD} --no_save \
        --rundir=$DEVICE_PATH \
        --pidfile=$DEVICE_PATH/twistd.pid \
        --python=$DEVICE_PATH/buildbot.tac
    sleep 1
    tail $DEVICE_PATH/twistd.log
    popd
fi
