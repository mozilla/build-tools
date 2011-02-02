#!/bin/bash
set -e
SCRIPTS_DIR="$(readlink -f $(dirname $0)/../..)"

HERE=$(dirname $(readlink -f $0))
if [ -z "$HG_REPO" ]; then
    export HG_REPO="http://hg.mozilla.org/mozilla-central"
fi

if [ -f "$PROPERTIES_FILE" ]; then
    PYTHON="/tools/python/bin/python"
    JSONTOOL="$PYTHON $SCRIPTS_DIR/buildfarm/utils/jsontool.py"

    builder=$($JSONTOOL -k properties.buildername $PROPERTIES_FILE)
    slavename=$($JSONTOOL -k properties.slavename $PROPERTIES_FILE)
    master=$($JSONTOOL -k properties.master $PROPERTIES_FILE)

    builddir=$(basename $(readlink -f ..))
    branch=$(basename $HG_REPO)

    # Clobbering
    if [ -z "$CLOBBERER_URL" ]; then
        export CLOBBERER_URL="http://build.mozilla.org/clobberer"
    fi

    python $SCRIPTS_DIR/clobberer/clobberer.py -s build $CLOBBERER_URL $branch \
        $builder $builddir $slavename $master

    # Purging
    python $SCRIPTS_DIR/buildfarm/maintenance/purge_builds.py \
        -s 4 -n info -n 'rel-*' -n $builddir
fi

python $SCRIPTS_DIR/buildfarm/utils/hgtool.py --tbox $HG_REPO src || exit 2
if [ ! -d objdir ]; then
    mkdir objdir
fi
cd objdir

# Setup a basic mozconfig file
echo '. $topsrcdir/browser/config/mozconfig' > mozconfig
echo 'ac_add_options --enable-valgrind' >> mozconfig
echo 'ac_add_options --with-ccache' >> mozconfig
echo 'ac_add_options --disable-jemalloc' >> mozconfig
echo 'CC=/tools/gcc-4.3.3/installed/bin/gcc' >> mozconfig
echo 'CXX=/tools/gcc-4.3.3/installed/bin/g++' >> mozconfig

if [ "`uname -m`" = "x86_64" ]; then
    export LD_LIBRARY_PATH=/tools/gcc-4.3.3/installed/lib64
else
    export LD_LIBRARY_PATH=/tools/gcc-4.3.3/installed/lib
fi

make -f ../src/client.mk MOZCONFIG=$PWD/mozconfig configure || exit 2
make -j4 || exit 2
make package || exit 2

debugger_args="--error-exitcode=1 --smc-check=all --gen-suppressions=all --leak-check=full"
suppression_file=$HERE/${MACHTYPE}.sup
if [ -f $suppression_file ]; then
    debugger_args="$debugger_args --suppressions=$suppression_file"
fi

export OBJDIR=.
python _profile/pgo/profileserver.py --debugger=valgrind --debugger-args="$debugger_args" || exit 1
