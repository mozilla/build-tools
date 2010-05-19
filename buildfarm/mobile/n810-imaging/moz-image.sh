#!/bin/bash
ROOTFS=$1
SDDEV=$2
UNITNAME=$3
RSYNC=rsync2
LOGFILE="debug-$(basename $SDDEV).log"

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
      echo "Copying imaging log to device"
      if [[ -f $LOGFILE ]] ; then
          cp $LOGFILE ${MOUNT}/imglog
      fi
    fi
  fi
  exit 1
}

function batchmode {
  if [ "x$BATCH" == "x" ] ; then
    warn "You are about to ERASE ${SDDEV}.  ARE YOU SURE? y/n"
      read a
      if [[ $a == "N" || $a == "n" ]]; then
        error "User exited by choice"
      else
        echo "gonna do it"
      fi
  else
    info "Imaging in batch mode. Redirecting output to $LOGFILE"
    exec &> $LOGFILE
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
  $RSYNC -a $ROOTFS/. $MOUNT/. &> /dev/null || error "could not copy files to $MOUNT"
  date > $MOUNT/img-success || error "could not create moz-verify.sh signal file"
}

function modify_image {
  info "Modifying Image"
  if [[ -d rootfs ]] ; then
    info 'rsyncing rootfs dir into image'
    chmod -R +x rootfs || error "setting mozilla scripts permissions"
    $RSYNC -a rootfs/. ${MOUNT}/. &> /dev/null || error "could not copy mozilla scripts onto card"
    rm $MOUNT/sentinel || error "Could not remove sentinel"
  else
    info 'missing rootfs directory -- no mozilla scripts will be installed'
  fi
  echo $UNITNAME > ${MOUNT}/etc/hostname
}

function eject {
  info "Unmounting"
  sync
  STATUS=0
  while [ $STATUS -eq 0 ] ; do
    for i in `mount | cut -f1 -d ' ' | grep $SDDEV` ; do
      umount $i &> /dev/null || warn "could not umount $i"
    done
    mount | grep $SDDEV > /dev/null
    STATUS=$?
  done
}

if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
fi
if [[ "x$1" == "x" || "x$2" == "x" || "x$3" = "x" ]] ; then
  error "Usage: moz-image.sh <rootfsdir> <sd card dev> <unit name>"
else
  MOUNT="`basename $SDDEV `-$$"
  batchmode
  eject
  partition
  copy
  modify_image
  eject
  sleep 2
  rm -rf $MOUNT
  echo
  info "Success on $SDDEV"
  rmdir $MOUNT || error "Mountpoint $MOUNT is not empty"
  exit 0
fi
