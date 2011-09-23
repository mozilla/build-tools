#!/bin/sh -x
cd /builds

if [ -z $1 ] ; then
  tegras=tegra-*
  stimer=60
else
  tegras=$1
  stimer=5
fi

for i in ${tegras}; do
  if [ -d $i ] ; then
    cd $i
    if [ ! -e clientproxy.pid ] ; then
      python clientproxy.py -b --tegra=$i
      sleep ${stimer}
    fi
    cd ..
  fi
done

