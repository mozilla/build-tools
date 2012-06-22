#!/bin/sh
cd /builds

# Use facter to distinguish between puppetized linux and mac
if [ -n "`facter hostname 2>/dev/null`" ] ; then
   . /tools/buildbot/bin/activate
fi

set -x

if [ "$TERM" != "screen" ] ; then
  "echo ERROR: Must run while attached to a screen. Use \|screen -x\|."
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

set +x

if [ -n "`facter hostname 2>/dev/null`" ] ; then
  deactivate
fi

echo start_cp.sh finished, remember to DETATCH from your screen session not
echo quit it! Do so correctly with: C-a d
