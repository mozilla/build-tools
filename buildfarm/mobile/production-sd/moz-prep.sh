#!/bin/bash
FLASHER="./flasher-3.0"
FIASCO="RX-44*.bin"
IMAGE="empty.jffs2"
USBPATTERN="Firmware"

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

function set_root {
  $FLASHER --enable-rd-mode
  $FLASHER --set-root-device mmc
}


if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
fi


while [ true ] ; do
  flash_image '--flash-only nolo,kernel,initfs --fiasco' $FIASCO
  flash_image '--rootfs' $IMAGE
  set_root
  while lsusb | grep $USBPATTERN ; do
    sleep 1
    echo "UNPLUG DEVICE"
  done
done

