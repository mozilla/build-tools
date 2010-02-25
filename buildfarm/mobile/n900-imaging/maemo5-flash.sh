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
# The Original Code is Maemo5 Flashing Automation.
#
# The Initial Developer of the Original Code is
# Mozilla Corporation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   John Ford <john@johnford.info>
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
FLASHER='flasher-3.5'
if [[ `uname | grep 'Darwin'` ]] ; then
    USBCMD="ioreg"
elif [[ `uname | grep 'Linux'` ]] ; then
    USBCMD="lsusb"
else
    echo 'ERROR: Only Linux and Darwin (Mac OS X) are supported'
    echo '       and you are running `uname`'
    exit 1
fi
FIASCO_MAIN='RX-51_2009SE_2.2009.51-1_PR_COMBINED_MR0_ARM.bin'
FIASCO_MAIN_SHA1='9f029310beb697757a543f1e1862bf87886b3ba3'
FIASCO_EMMC='RX-51_2009SE_1.2009.41-1.VANILLA_PR_EMMC_MR0_ARM.bin'
FIASCO_EMMC_SHA1='a2a096742f43463d48fcbc677cd9cca755127f55'
ROOTFS_FILE=$1

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 1>&2
   exit 1
fi

if [[ ! -f $ROOTFS_FILE ]] ; then
    echo 'ERROR: Root filesystem does not exist'
    exit 1
fi
if [[ ! -f $FIASCO_MAIN ]] ; then
    echo 'ERROR: Main fiasco image not found'
    exit 1
fi
if [[ ! -f $FIASCO_EMMC ]] ; then
    echo 'ERROR: Emmc fiasco image not found'
    exit 1
fi
if [[ -x "./$FLASHER" ]] ; then
    FLASHER="./$FLASHER"
else
    #Flasher not found in directory, look in path
    if [[ ! -x `which $FLASHER` ]] ; then
	echo "ERROR: Flasher with execute permissions not found"
    fi
fi
FLASHER_TEST=`$FLASHER &> /dev/null`
if [[ $FLASHER_TEST == 126 ]] ; then
    echo 'ERROR: The $FLASHER provided does not run on this system'
    echo '       you are trying to run a `file $FLASHER` '
    echo '       binary on `uname`'
    exit 1
fi

echo "********************************************************************************"
echo "*"
echo "* Welcome to the Mozilla N900 Flashing Tool"
echo "*"
echo "* flaser-3.5:    $FLASHER"
echo "* main fiasco:   $FIASCO_MAIN"
echo "* maps fiasco:   $FIASCO_EMMC"
echo "* rootfs:        $ROOTFS_FILE"
echo "*"
echo "********************************************************************************"


#Check that we are using the correct files.  Flasher does understand
#how to do checksumming I think, but we need a specific version of
#the image.

#This is broken currently
# FIASCO_MAIN_RUNTIME_SHA1=`openssl sha1 < $FIASCO_MAIN`
# FIASCO_EMMC_RUNTIME_SHA1=`openssl sha1 < $FIASCO_EMMC`
# if [[ ! "$FIASCO_MAIN_SHA1" == "$FIASCO_MAIN_RUNTIME_SHA1" ]] ; then
#     echo 'ERROR: Mismatched checksum for main fiasco image'
#     exit 1
# fi
# if [[ ! "$FIASCO_EMMC_SHA1" == "$FIASCO_EMMC_RUNTIME_SHA1" ]] ; then
#     echo 'ERROR: Mismatched checksum for emmc fiasco image'
#     exit 1
# fi

while true ; do
    FLASH_STRING="Nokia Mobile Phones E61 (Firmware update mode)"
    PCMODE_STRING="N900 (PC-Suite Mode)"
    EMMC_STRING="Nokia N900 (Update mode)"
    EMMC_STRING2="Nokia Mobile Phones"
    STORAGE_STRING="N900 (Storage Mode)"
    if [[ `$USBCMD | grep "$EMMC_STRING"` ||
	  `$USBCMD | grep "$EMMC_STRING2"` ||
	  `$USBCMD | grep "$STORAGE_STRING"` ||
	  `$USBCMD | grep "$PCMODE_STRING"` ]] ; then
	echo "ALERT: Device is not in correct mode"
	echo "1) remove batter and unplug cable"
	echo "2) replace battery"
	echo "3) press and hold U key"
	echo "4) while hold U down, insert USB cable"
	echo "If device is still not in correct mode use dev cradle"
	printf "%b" "\a"
	sleep 2
	continue
    fi
    $FLASHER --enable-rd-mode
    $FLASHER -F $FIASCO_MAIN -f
    if [ $? != 0 ] ; then
	echo "ERROR: $FLASHER did not flash main image correctly"
	exit 1
    fi
    $FLASHER -r $ROOTFS_FILE -f
    if [ $? != 0 ] ; then
	echo "ERROR $FLASHER failed to flash the mozilla root filesystem image"
	exit 1
    fi
    $FLASHER -F $FIASCO_EMMC -f
    if [ $? != 0 ] ; then
	echo "ERROR $FLASHER failed to flash the eMMC filesystem image"
	exit 1
    fi
    while [[ `$USBCMD | grep "$FLASH_STRING"` ||
	     `$USBCMD | grep "$PCMODE_STRING"` ||
	     `$USBCMD | grep "$EMMC_STRING"` ||
	     `$USBCMD | grep "$EMMC_STRING2"` ||
	     `$USBCMD | grep "$STORAGE_STRING"` ]] ; do
	printf "%b" "UNPLUG N900\a\n"
	echo "Reseat battery, turn on and run \"sudo i NNN\" on device"
	sleep 1
    done
done
