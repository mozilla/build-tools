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

tegras=`ls -d tegra-* 2&> /dev/null`
pandas=`ls -d panda-* 2&> /dev/null`

if [ -z $1 ] ; then
  devices="$tegras $pandas"
  stimer=60
else
  devices=$1
  stimer=5
fi

if [ -n "$pandas" -a -n "$tegras" ] ; then
   # Preserve the assertion that a single foopy won't handle both device types
   echo ERROR: Found both panda-* and tegra-* in directory.
   exit 1
fi

for i in ${devices}; do
  if [ -d $i ] ; then
    cd $i
    if [ ! -e clientproxy.pid ] ; then
      python clientproxy.py -b --device=$i
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
