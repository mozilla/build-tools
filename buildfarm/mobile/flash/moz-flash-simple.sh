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
FIASCO='RX-44_DIABLO_5.2008.43-7_PR_COMBINED_MR0_ARM.bin'
ROOTFS=$1
FLASHER='./flasher-3.0'
USBPATTERN='Nokia'

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

function greet {
  draw_line
  echo "Welcome to MozFlash"
  draw_line
  info "Using FIASCO image at '$FIASCO'"
  info "Using RootFS image at '$ROOTFS'"
  info "Using Flasher program '$FLASHER'" 
  #info "Setting hostname to   '$HOSTNAME'"
}

function flash_image {
  FLAG=$1
  FILE=$2
  $FLASHER $FLAG $FILE --flash 
  RC=$?
  if [ $RC == 3 ] ; then
    error "Lost USB Connection while flashing ${FILE}.  Dead battery?"
  elif [ $RC != 0 ] ; then
    error "There was an error trying to flash $FILE. RC=$?"
  fi
}


if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
fi

if [ "x$1" == "x" ]; then
  error "You must specify an root filesystem directory"
fi

while [ true ] ; do
  greet
  flash_image '--fiasco' $FIASCO
  flash_image '--rootfs' $ROOTFS
  $FLASHER --enable-rd-mode
  $FLASHER --set-root-device flash
  while lsusb | grep $USBPATTERN ; do
    sleep 1
    echo "UNPLUG DEVICE"
  done
done
