#!/bin/bash
FIASCO='RX-44_DIABLO_5.2008.43-7_PR_COMBINED_MR0_ARM.bin'
ROOTFS=$1
HOSTNAME='cest-ne-pas-une-n810'
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
  info "Setting hostname to   '$HOSTNAME'"
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

if [ "x$2" == "x" ]; then 
  warn "Using default hostname of $HOSTNAME"
else
  HOSTNAME=$2
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
