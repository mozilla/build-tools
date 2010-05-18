#!/bin/bash
SDDEV=$1
IMGNAME=$2
RSYNC=rsync2

function info {
  echo "INFO($SDDEV): $1"
}

function warn {
  echo "WARN($SDDEV): $1"
}

function error {
  echo "ERROR!($SDDEV): $1"
  exit
}

function copy {
  info "Copying data from card"
  if [[ -d $IMGNAME ]] ; then
      error 'I will not overwrite another image'
  fi
  mkdir $IMGNAME $MOUNT || error "could not create $MOUNT directory"
  mount -t ext2 ${SDDEV}1 $MOUNT || error "could not mount $SDDEV on $MOUNT"
  $RSYNC -a $MOUNT/. $IMGNAME/. || error "could not copy files to $IMGNAME"
}

function clean_image {
  info "Cleaning up image"
  rm -f $IMGNAME/var/log/uptime.log
  rm -f $IMGNAME/sentinel

}

function eject {
  info "Unmounting"
  sync
  if [[ `mount | grep ${SDDEV}1` ]] ; then
      umount ${SDDEV}1 || warn "could not umount root-fs/${SDDEV}1"
  fi
  if [[ `mount | grep ${SDDEV}2` ]] ; then
      umount ${SDDEV}2 || warn "could not umount root-fs/${SDDEV}2"
  fi
  rm -rf $MOUNT
}


if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
fi
if [[ "x$1" == "x" || "x$2" == "x" ]] ; then
  error "Usage: moz-get-image.sh <sd card dev> <image name>"
else
  MOUNT="`basename $SDDEV `-$$"
  eject
  copy
  clean_image
  eject
  sleep 2
  rm -rf $MOUNT
  echo "All done on $SDDEV"
fi
