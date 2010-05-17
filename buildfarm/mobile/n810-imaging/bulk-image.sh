#!/bin/bash
# Useful for finding out which devices: find /dev | grep "/dev/sd.[0-9]"
ROOTFSDIR='moz-n810-v1'


if [ $# -eq 0 ] ; then
  echo Please specify devices from this list
  echo "WARNING: DO NOT SELECT A NON-SD CARD DRIVE LETTER" 
  find /dev -maxdepth 1 -name sda -o -name sd? -print
fi

for i in "$@" ; do
  if [[ "$i" == "a" || "$i" == "A" ]] ; then
    echo Ignoring /dev/sda
  fi
  BATCH='yes' ./moz-image.sh $ROOTFSDIR /dev/sd${i} maemo-n810-XX &
done

wait
echo "BULK IMAGING COMPLETED"
