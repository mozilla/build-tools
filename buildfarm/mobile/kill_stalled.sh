#!/bin/sh

cd /builds

if [ -z $1 ] ; then
  echo "usage: kill_stalled.sh ### [### ...]"
  echo "       where ### is the tegra id (without the tegra- part)"
else
  for tegra in $* ; do
    if [ -d tegra-$tegra ] ; then
      stalled=`ps auxw | grep server.js | grep tegra-${tegra} | awk '{print $2}'`
      if [ ! -z $stalled ] ; then
        kill ${stalled}
        echo tegra-${tegra} stalled server.js at PID ${stalled} killed
        now=`date +%Y%m%d%H%M%S`
        echo ${now},tegra-${tegra},stalled >> /builds/tegra_events.log
      else
        echo tegra-${tegra} none found
      fi
    else
      echo skipping tegra-${tegra}
    fi
  done
fi

