#!/bin/sh -x
cd /builds

if [ -z $1 ] ; then
  tegras=`ls -d tegra-* 2> /dev/null`
  pandas=`ls -d panda-* 2> /dev/null`
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

