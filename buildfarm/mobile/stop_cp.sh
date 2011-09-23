#!/bin/sh -x
cd /builds

if [ -z $1 ] ; then
  tegras=tegra-*
else
  tegras=$1
fi

for i in ${tegras}; do
  if [ -d $i ] ; then
    if [ -e $i/clientproxy.pid ] ; then
      python sut_tools/stop.py -t $i
      sleep 5
      ps auxww | grep "${i}"
    fi
  fi
done

