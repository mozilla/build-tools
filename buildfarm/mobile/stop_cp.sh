#!/bin/sh -x
cd /builds

if [ -z $1 ] ; then
  tegras=tegra-*
  pandas=panda-*
  devices="$tegras $pandas"
else
  devices=$1
fi

for i in ${devices}; do
  if [ -d $i ] ; then
    if [ -e $i/clientproxy.pid ] ; then
      python sut_tools/stop.py --device $i
      sleep 5
      ps auxww | grep "${i}"
    fi
  fi
done

