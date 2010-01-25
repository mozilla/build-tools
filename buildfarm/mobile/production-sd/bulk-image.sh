#!/bin/bash
# Useful for finding out which devices: find /dev | grep "/dev/sd.[0-9]"
ROOTFSDIR='moz-ref-sd-v5'

EXCLUDE_FILE=/flashing/exclude_list.txt

if [ $# -eq 0 ] ; then
  echo Please specify devices from this list
  devlist=`find /dev -maxdepth 1 -name sd?`
  for i in $devlist; do
    grep -q "$i" $EXCLUDE_FILE
    if [ $? -ne 0 ] ; then
      echo $i
    fi
  done
fi

for i in "$@" ; do
  BATCH='yes' ./moz-image.sh $ROOTFSDIR /dev/sd${i} maemo-n810-ref &
done

wait
echo "BULK IMAGING COMPLETED"
