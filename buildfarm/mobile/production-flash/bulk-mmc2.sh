#!/bin/bash
# Useful for finding out which devices: find /dev | grep "/dev/sd.[0-9]"

if [ $# -eq 0 ] ; then
  echo Please specify devices from this list
  find /dev/ | grep "/dev/sd[^a][0-9]"
fi

for i in "$@" ; do
  ./moz-mmc2-prep.sh /dev/sd${i} &
done

wait
