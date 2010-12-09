#! /bin/bash
#  initscript for buildbot

# chkconfig: 2345 50 08
### BEGIN INIT INFO
# Provides:          buildbot
# Required-Start:    $local_fs $network puppet
# Should-Start:      $remote_fs 
# Should-Stop:       $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      K 0 1 6
# Short-Description: Buildbot
# Description:       Buildbot
### END INIT INFO

# MOZILLA DEPLOYMENT NOTES
# - This file is distributed by Puppet to all linux build servers
# - it lives in the build/tools repo at buildbot-helpers/startup/linux-initd-buildbot.sh

# Required-Stop:     $local_fs
PATH=/sbin:/bin:/usr/sbin:/usr/bin
DESC="Buildbot"

BUILDSLAVE_CMD=/tools/buildbot/bin/buildbot # will change to 'buildslave' in 0.8.1
LOCKFILE=/var/lock/subsys/buildbot
RUNSLAVE=/usr/local/bin/runslave.py
PYTHON=/tools/python/bin/python

test -x ${BUILDSLAVE_CMD} || exit 0

. /lib/lsb/init-functions

start_buildbot() {
    # note - spaces here will break things
    su - cltbld sh -c "${PYTHON} ${RUNSLAVE}"
    ret=$?
    if [ $ret == "0" ]; then
        touch ${LOCKFILE}
    fi
    return $ret
}

do_start () {
    errors=0
	echo "Starting buildslave"
	if start_buildbot 
	then
	    echo "started"
	else
	    echo "not started"
	    errors=$(($errors+1))
	fi
    return $errors
}

do_stop () {
    echo "sorry, no-can-do.  This script is a one-way-trip to start the buildslave."
    return 1
}

do_reload () {
    do_stop
}

do_restart () {
    do_stop
}

case "$1" in
  start)
  	do_start
  	exit $?
	;;
  stop)
  	do_stop
  	exit $?
	;;
  reload)
  	do_reload
  	exit $?
	;;
  restart|force-reload)
  	do_restart
  	exit $?
	;;
  *)
	log_warning_msg "Usage: $0 {start|stop|restart|reload|force-reload}"
	exit 1
	;;
esac

exit 0

