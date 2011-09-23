#!/bin/sh

for TEGRA in tegra-* ; do
  if [ -d /builds/$TEGRA ]; then
    echo pushing SUTAgent.ini to $TEGRA
    python sut_tools/pushfile.py $TEGRA /builds/SUTAgent.ini /data/data/com.mozilla.SUTAgentAndroid/files/SUTAgent.ini

    echo pushing watcher.ini to $TEGRA
    python sut_tools/pushfile.py $TEGRA /builds/watcher.ini /data/data/com.mozilla.watcher/files/watcher.ini
  fi
done

