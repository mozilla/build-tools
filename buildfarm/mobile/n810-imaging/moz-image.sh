#!/bin/bash
ROOTFS=$1
SDDEV=$2
UNITNAME=$3
RSYNC=rsync2

function info {
  echo "INFO($SDDEV): $1"
}

function warn {
  echo "WARN($SDDEV): $1"
}

function error {
  echo "ERROR!($SDDEV): $1"
  if [[ x"$MOUNT" != "x" ]] ; then
    if [[ `mount | grep $MOUNT` ]] ; then
      echo "This card is defective! Imaging attempted `date`" > ${MOUNT}/sentinel
    fi
  fi
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

function partition {
  info "Partitioning $SDDEV"
  dd if=/dev/zero of=${SDDEV} bs=512 count=1 &> /dev/null || error "failed to reset partition table"
  parted --script ${SDDEV} mktable msdos || error "failed creating partition table"
  parted --script ${SDDEV} mkpart primary 0 1800 || error "failed to create root partition"
  parted --script ${SDDEV} mkpart primary 1801 3800 || error "failed to create data partition"
  sync
  sleep 5
  info "Formatting Drives"
  mkfs.ext2 -q ${SDDEV}1 -L root-fs || error 'failed to format rootfs'
  mkfs.ext2 -q ${SDDEV}2 -L scratch || error 'failed to format scratch'
  sync
  sleep 2
}

function copy {
  info "Copying data to card"
  mkdir $MOUNT || error "could not create $MOUNT directory"
  mount -t ext2 ${SDDEV}1 $MOUNT || error "could not mount $SDDEV on $MOUNT"
  $RSYNC -a $ROOTFS/. $MOUNT/. || error "could not copy files to $MOUNT"
}

function modify_image {
  info "Modifying Image"
  if [[ -d rootfs ]] ; then
    info 'rsyncing rootfs dir into image'
    $RSYNC -a rootfs/. ${MOUNT}/.
  fi
  echo $UNITNAME > ${MOUNT}/etc/hostname

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
if [[ "x$1" == "x" || "x$2" == "x" || "x$3" = "x" ]] ; then
  error "Usage: moz-image.sh <rootfsdir> <sd card dev> <unit name>"
else
  warning
  MOUNT="`basename $SDDEV `-$$"
  eject
  partition
  copy
  modify_image
  eject
  sleep 2
  rm -rf $MOUNT
  echo "All done on $SDDEV"
fi
