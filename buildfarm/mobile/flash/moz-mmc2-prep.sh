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
