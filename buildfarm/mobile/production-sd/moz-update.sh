#!/bin/bash
ROOTFS=$1
SDDEV=$2
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

function copy {
  info "Copying data to card"
  mkdir $MOUNT || error "could not create $MOUNT directory"
  mount -t ext2 ${SDDEV}1 $MOUNT || error "could not mount $SDDEV on $MOUNT"
  $RSYNC -av --delete $ROOTFS/. $MOUNT/. || error "could not copy files to $MOUNT"
}

function modify_image {
  info "Modifying Image"
  #echo $UNITNAME > ${MOUNT}/etc/hostname
  echo "Updated from \"${ROOTFS}\" at `date`" >> ${MOUNT}/builds/buildbot/info/admin

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
  error "Usage: moz-update.sh <rootfsdir> <sd card dev>"
else
  MOUNT="`basename $SDDEV `-$$"
  eject
  copy
  modify_image
  eject
fi
