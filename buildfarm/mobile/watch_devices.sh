#!/bin/bash -eu
PYTHON=`which python`

# MAGIC NUMBERS (global)
# used to determine how long we sleep when...
SUCCESS_WAIT=200 # ... seconds after we startup buildbot
FAIL_WAIT=500 # ... seconds after we stop buildbot due to error.flg

# boilerplate
warn() { for m; do echo "$m"; done 1>&2; }
die() { warn "$@" >&2 ; exit 1 ; }
usage() { warn "$@" "${USAGE:-}" ; test $# -eq 0; exit $?; }

log() {
  local ts=`date +"%Y-%m-%d %H:%M:%S"`
  warn "$ts -- $@" ;
}
debug() { true; } # No actual debug logging yet
death() {
  local ts=`date +"%Y-%m-%d %H:%M:%S"`
  die "$ts -- $@" ;
}

function log_output_to() {
  # $1 is "where to
  # $2 (if present) is "hide output to invoker"
  if [ ! -z "${2:-}" ]; then
    # Redirect all output
    exec >>$1 2>&1
  else
    # Tee all output instead
    exec > >(tee -a $1) 2>&1
  fi
}

function check_buildbot_running() {
  # returns success if running
  #         !0 if not running
  local device=$1
  if [ ! -f /builds/$device/twistd.pid ]; then
     return 1
  fi
  local expected_pid=`cat /builds/$device/twistd.pid`
  debug "buildbot pid is $expected_pid"
  local retcode=0
  kill -0 $expected_pid 2>&1 > /dev/null || retcode=$?
  return $retcode
}

function kill_lockfile() {
  # $1 is device name
  rm -f /builds/$1/watcher.lock
}

function device_check_exit() {
  kill_lockfile $1
  log "Cycle for our device ($1) complete"
}

function device_check() {
  local device=$1
  log_output_to "/builds/$device/watcher.log" hide
  export PYTHONPATH=/builds/sut_tools
  deviceIP=`python -c "import sut_lib;print sut_lib.getIPAddress('$device')" 2> /dev/null`
  local retcode=0
  lockfile -r0 /builds/$device/watcher.lock 2>&1 > /dev/null || retcode=$?
  if [ $retcode -ne 0 ]; then
    die "failed to aquire lockfile"
  fi
  log "Starting cycle for our device ($device) now"
  # Trap here, not earlier so that if lockfile fails, we don't clear the lock
  # From another process
  trap "device_check_exit $device" EXIT
  local buildbot_running=0
  check_buildbot_running $device || buildbot_running=$?
  if [ $buildbot_running -ne 0 ]; then
    if [ -f /builds/$device/disabled.flg ]; then
       death "Not Starting due to disabled.flg"
    fi
    if [ -f /builds/$device/error.flg ]; then
      # Clear flag if older than an hour
      if [ `find /builds/$device/error.flg -mmin +60` ]; then
        log "removing $device error.flg and trying again"
        rm -f /builds/$device/error.flg
      else
        death "Error Flag told us not to start"
      fi;
    fi
    export SUT_NAME=$device
    export SUT_IP=$deviceIP
    retcode=0
    $PYTHON /builds/sut_tools/verify.py $device || retcode=$?
    if [ $retcode -ne 0 ]; then
       if [ ! -f /builds/$device/error.flg ]; then
           echo "Unknown verify failure" | tee "/builds/$device/error.flg"
       fi
       death "Verify failed"
    fi;
    /builds/tools/buildfarm/mobile/manage_buildslave.sh start $device
    log "Sleeping for ${SUCCESS_WAIT} sec after startup, to prevent premature flag killing"
    sleep ${SUCCESS_WAIT} # wait a bit before checking for an error flag or otherwise
  else # buildbot running
    log "(heartbeat) buildbot is running"
    if [ -f /builds/$device/error.flg -o -f /builds/$device/disabled.flg ]; then
        log "Something wants us to kill buildbot..."
        set +e # These steps are ok to fail, not a great thing but not critical
        cp /builds/$device/error.flg /builds/$device/error.flg.bak # stop.py will remove error flag o_O
        python /builds/sut_tools/stop.py --device $device
        # Stop.py should really do foopy cleanups and not touch device
        SUT_NAME=$device python /builds/sut_tools/cleanup.py $device
        mv /builds/$device/error.flg.bak /builds/$device/error.flg # Restore it
        set -e
        log "sleeping for ${FAIL_WAIT} seconds after killing, to prevent startup before master notices"
        sleep ${FAIL_WAIT} # Wait a while before allowing us to turn buildbot back on
    fi;
  fi;
  exit
}


function watch_launcher(){
  echo "STARTING Watcher"
  log_output_to /builds/watcher.log
  ls -d /builds/{tegra-*[0-9],panda-*[0-9]} 2>/dev/null | sed 's:.*/::' | while read device; do
    log "..checking $device"
    "${0}" "${device}" &
  done
  log "Watcher completed."
}

if [ "$#" -eq 0 ]; then
   watch_launcher;
else
   device_check $1 ;
fi;
