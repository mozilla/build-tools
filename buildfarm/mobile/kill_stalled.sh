#!/bin/sh

cd /builds

if [ -z $1 ] ; then
  echo "usage: kill_stalled.sh ### [### ...]"
  echo "       where ### is the tegra id (without the tegra- part)"
else
  for tegra in $* ; do
    if [ -d tegra-$tegra ] ; then
      echo killing any stray processes from tegra-$tegra
      python ./sut_tools/tegra_checkstalled.py tegra-$tegra
    else
      echo skipping tegra-${tegra}
    fi
  done
fi

