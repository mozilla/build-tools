#!/bin/bash
SDDEV=$1
UNITNAME=$2
RSYNC=./moz-rsync

function info {
  echo "INFO: $1"
}

function warn {
  echo "WARN: $1"
}

function error {
  echo "ERROR! $1"
  exit
}


function modify_image {
  info "Mounting card"
  mkdir $MOUNT || error "could not create $MOUNT directory"
  mount -t ext2 ${SDDEV}1 $MOUNT || error "could not mount $SDDEV on $MOUNT"
  info "Modifying card"
  echo $UNITNAME > ${MOUNT}/etc/hostname
  echo "Hostname set at `date`" >> ${MOUNT}/builds/buildbot/info/admin

}

function eject {
  info "Unmounting"
  sync
  umount ${SDDEV}1 || warn "could not umount $SDDEV"
  rm -rf $MOUNT
}

if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
fi
if [[ "x$1" == "x" || "x$2" == "x" ]] ; then
  error "Usage: moz-image.sh <sd card dev> <unit name>"
else
  MOUNT="`basename $SDDEV `-$$"
  eject
  modify_image
  eject
fi
