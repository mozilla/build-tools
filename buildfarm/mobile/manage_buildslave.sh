#!/bin/bash
if [ -d "/tools/buildbot/bin" ]; then
  BB_PATH=/tools/buildbot/bin/buildslave
  BB_PYTHON=/tools/buildbot/bin/python2.7
  BB_TWISTD=/tools/buildbot/bin/twistd
else
  BB_PATH=`which buildslave`
  BB_PYTHON=`which python`
  BB_TWISTD=`which twistd`
fi
hash "$BB_PATH" "$BB_PYTHON" "$BB_TWISTD" 2>/dev/null || \
    (echo "Can't find all needed executables to manage buildslave" >&2; exit 1)

OPTIONS="gettac start stop restart"

opt="$1"

if [ -z "$opt" ]; then
    echo "You can call this script with the following options:" >&2
    echo "$OPTIONS" >&2
    exit 2
else
    if [ -z $2 ]; then
        echo "You have to specify which device to manage." >&2
        exit 2
    fi
    DEVICE="${2}"
    DEVICE_PATH="/builds/${DEVICE}"
    if [ ! -d "$DEVICE_PATH" ]; then
        echo "Directory '$DEVICE_PATH' does not exist. Try again with the correct device name." >&2
        exit 64
    fi
fi

case "${opt}" in
    gettac)
        rm $DEVICE_PATH/buildbot.tac
        wget -q "-O${DEVICE_PATH}/buildbot.tac" "http://slavealloc.build.mozilla.org/gettac/${DEVICE}"
        ;;
    stop)
        "${BB_PATH}" stop "${DEVICE_PATH}"
        ;;
    restart)
        "${BB_PATH}" stop "${DEVICE_PATH}"
        # also perform 'start' actions - following line 'falls through' to start) section
        # to achieve exactly this
        ;&
    start)
        echo "We want to always start buildbot through twistd"
        echo "We will run with the twistd command instead of calling buildslave"
        pushd "${DEVICE_PATH}"
        # should be in quotes in case we have a space in a parent directory name
        "${BB_PYTHON}" "${BB_TWISTD}" --no_save \
            "--rundir=$DEVICE_PATH" \
            "--pidfile=$DEVICE_PATH/twistd.pid" \
            "--python=$DEVICE_PATH/buildbot.tac"
        sleep 1
        tail twistd.log
        popd
        ;;
    *)
esac
