#!/bin/sh -x
cd /builds

if [ "$TERM" != "screen" ] ; then
  "echo ERROR: Must run while attached to a screen. Use \|screen -x\|.""
  exit 1
fi

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

echo start_cp.sh finished, remember to DETATCH from your screen session not
echo quit it! Do so correctly with: C-a d
