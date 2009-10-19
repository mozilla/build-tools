#!/bin/bash
DEVICE=$1
MOUNT=`basename ${DEVICE}-$$-mount`

function draw_line {
  echo "====================================="
}

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

mkfs.vfat ${DEVICE}1 || error "Failed to create fat fs"
mkdir $MOUNT || error "Failed to create mount point $MOUNT"
mount -t vfat ${DEVICE}1 $MOUNT || error "Failed to mount $DEVICE on $MOUNT"
info "rsync starting"
rsync -a mmc2/. $MOUNT/. 2> /dev/null || warn "Issues copying files.  Likely because of vfat not having permissions"
info "rsync complete"
sync
info "fs sync complete"
umount $MOUNT || error "Failed to unmount device"
rm -rf $MOUNT || "Couldn't remove mount point $MOUNT"
info "process complete for $DEVICE"
