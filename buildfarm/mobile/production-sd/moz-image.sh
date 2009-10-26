#!/bin/bash
ROOTFS=$1
SDDEV=$2
UNITNAME=$3
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

function warning {
  if [ "x$BATCH" == "x" ] ; then
    warn "You are about to ERASE ${SDDEV}.  ARE YOU SURE? y/n"
      read a
      if [[ $a == "N" || $a == "n" ]]; then
        error "User exited by choice"
      else
        echo "gonna do it"
      fi
  else
    info "You are formating $SDDEV in batch mode"
  fi
}

function dual_partition {
  info "Partitioning $SDDEV"
  dd if=/dev/zero of=${SDDEV} bs=512 count=1 > /dev/null
  parted --script ${SDDEV} mktable msdos || error "failed creating partition table"
  parted --script ${SDDEV} mkpart primary 0 3000 || error "failed to create root partition"
  parted --script ${SDDEV} mkpart primary 3001 3800 || error "failed to create data partition"
  sync
  sleep 2
  info "Formatting Drives"
  mkfs.ext2 ${SDDEV}1 -L $UNITNAME
  mkfs.ext2 ${SDDEV}2 -L $UNITNAME
  sync
  sleep 2
}
function single_partition {
  info "Partitioning $SDDEV"
  dd if=/dev/zero of=${SDDEV} bs=512 count=1 > /dev/null
  parted --script ${SDDEV} mktable msdos || error "failed creating partition table"
  info "Formatting ${SDDEV}1"
  parted --script ${SDDEV} mkpartfs primary ext2 0 3900 || error "failed to create data partition"
  info "Syncing FS"
  sync
  sleep 1
}

function copy {
  info "Copying data to card"
  mkdir $MOUNT || error "could not create $MOUNT directory"
  mount -t ext2 ${SDDEV}1 $MOUNT || error "could not mount $SDDEV on $MOUNT"
  $RSYNC -a $ROOTFS/. $MOUNT/. || error "could not copy files to $MOUNT"
}

function modify_image {
  info "Modifying Image"
  echo $UNITNAME > ${MOUNT}/etc/hostname
  echo "Imaged from \"${ROOTFS}\" at `date`" > ${MOUNT}/builds/buildbot/info/admin

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
if [[ "x$1" == "x" || "x$2" == "x" || "x$3" = "x" ]] ; then
  error "Usage: moz-image.sh <rootfsdir> <sd card dev> <unit name>"
else
  warning
  MOUNT="`basename $SDDEV `-$$"
  eject
  dual_partition
  copy
  modify_image
  eject
  echo "All done on $SDDEV"
fi
