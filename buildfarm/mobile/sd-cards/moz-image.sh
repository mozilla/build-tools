#!/bin/bash
# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla specific maemo flashing scripts
#
# The Initial Developer of the Original Code is
# Mozilla Corporation.
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   John Ford <jford@mozilla.com>, Mozilla Corporation
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
ROOTFS=$1
SDDEV=$2
UNITNAME=$3
RSYNC=./moz-rsync

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
#  draw_line
#  info "Partitioning"
#  sfdisk $SDDEV << MBR
#0,,
#
#
#
#MBR
  dd if=/dev/zero of=${SDDEV} bs=512 count=1 > /dev/null
  parted --script ${SDDEV} mklabel msdos || error "failed creating partition table"
  parted --script ${SDDEV} mkpartfs primary ext2 0 3500 || error "failed to create data partition"
  parted --script ${SDDEV} mkpartfs primary linux-swap 3500 3900 || error "failed to create swap"
  sync
}

function format {
  draw_line
  info "Formatting"
  mkfs.ext2 -L $UNITNAME ${SDDEV}1 || error "could not format filesystem."
  echo mkswap ${SDDEV}2 || error "failed to format swap space"
  mkswap ${SDDEV}2 || error "failed to format swap space"
}

function copy {
  draw_line
  info "Copying data to card"
  mkdir $MOUNT || error "could not create $MOUNT directory"
  mount -t ext2 ${SDDEV}1 $MOUNT || error "could not mount $SDDEV on $MOUNT"
  $RSYNC -a $ROOTFS/. $MOUNT/. || error "could not copy files to $MOUNT"
}

function modify_image {
  draw_line 
  info "Modifying Image"
  #set machine hostname
  echo $UNITNAME > ${MOUNT}/etc/hostname
  echo "Imaged from \"${ROOTFS}\" at `date`" > /builds/buildbot/info/admin

}

function eject {
  draw_line
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
  partition
  format
  copy
  modify_image
  eject
fi
