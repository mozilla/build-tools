#!/bin/bash
# Useful for finding out which devices: find /dev | grep "/dev/sd.[0-9]"

if [ $# -eq 0 ] ; then
  echo Please specify devices from this list
  find /dev/ | grep "/dev/sd[^a]1"
fi

for i in "$@" ; do
  BATCH='yes' ./moz-image.sh moz-ref-sd-v4 /dev/sd${i} maemo-n810-ref > $i.log&
done

wait
