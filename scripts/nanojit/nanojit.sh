#!/bin/bash
set -e
SCRIPTS_DIR="$(dirname $0)/../.."

if [ -z "$HG_REPO" ]; then
    HG_REPO="http://hg.mozilla.org/projects/nanojit-central"
fi

python $SCRIPTS_DIR/buildfarm/utils/hgtool.py $HG_REPO nanojit-src
(cd nanojit-src; autoconf)

if [ ! -d nanojit-build ]; then
    mkdir nanojit-build
fi
cd nanojit-build
../nanojit-src/configure
make
make check
