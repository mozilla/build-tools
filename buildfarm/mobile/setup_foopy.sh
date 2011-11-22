#!/bin/bash -x

export PATH=/opt/local/bin:/opt/local/sbin:$PATH

if [ ! -d /builds ]; then
  mkdir /builds
fi

cd /builds

if [ ! -d /builds/talos-data ]; then
  mkdir /builds/talos-data
  cd /builds/talos-data

  hg clone http://hg.mozilla.org/users/tglek_mozilla.com/fennecmark bench@taras.glek
  hg clone http://hg.mozilla.org/build/pageloader pageloader@mozilla.org
  hg clone http://hg.mozilla.org/build/talos talos-repo
  ln -s /builds/talos-data/talos-repo/talos .
fi
if [ ! -d /builds/tools ]; then
  cd /builds
  hg clone http://hg.mozilla.org/build/tools tools

  cd /builds/tools/sut_tools
  ln -s /builds/talos-data/talos/devicemanager.py .
  ln -s /builds/talos-data/talos/devicemanagerADB.py .
  ln -s /builds/talos-data/talos/devicemanagerSUT.py .
fi
if [ ! -d /builds/sut_tools ]; then
  cd /builds
  ln -s /builds/tools/sut_tools sut_tools
fi
cd /builds

