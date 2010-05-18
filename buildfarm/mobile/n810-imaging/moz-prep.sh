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

function flash {
  ARGS=$@
  $FLASHER $ARGS &> flasher.log 
  RC=$?
  if [ $RC == 3 ] ; then
    echo ; echo ; echo;
    echo =============================
    cat flasher.log
    error "Lost USB Connection while flashing $FILE"
  elif [ $RC != 0 ] ; then
    echo ; echo ; echo ================
    error "There was an error trying to flash $FILE. RC=$?"
  fi
}  

function flash_image {
  FLAG=$1
  FILE=$2
  flash $FLAG $FILE --flash
}

function set_root {
  flash --enable-rd-mode
  flash --set-root-device mmc
}


if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
fi


while [ true ] ; do
  echo Plug MicroUSB cable, seat battery then plug in power cable  into N810 
  flash -i
  echo Resetting under way
  flash_image '--flash-only nolo,kernel,initfs --fiasco' $FIASCO
  flash_image '--rootfs' $IMAGE
  set_root
  STATUS=0
  echo "Completed Successfully"
  echo -n "Unplug N810 from computer or press CTRL+C to quit"
  while [ $STATUS -ne 1 ] ; do 
    lsusb | grep $USBPATTERN > /dev/null
    STATUS=$?
    echo -n '.'
    sleep 1
  done
  echo #for the new line
done

