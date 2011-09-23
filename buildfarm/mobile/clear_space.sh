#!/bin/sh -x
cd /builds

for i in tegra-* ; do
  rm -f /builds/$i/clientproxy.log.*
  rm -f /builds/$i/twistd.log.*
done

find /tmp/ -type d -mtime +1 -exec rm -rf {} \;

