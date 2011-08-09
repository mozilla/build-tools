#!/bin/bash
set -e
set -x
pushd $(dirname $0)/../../ > /dev/null
SCRIPTS_DIR=$PWD
popd > /dev/null

SPIDERDIR=$SCRIPTS_DIR/scripts/spidermonkey_builds

if [ -z "$HG_REPO" ]; then
    export HG_REPO="http://hg.mozilla.org/integration/mozilla-inbound"
fi

VARIANT=$1
if [ ! -f "$SPIDERDIR/$VARIANT" ]; then
    echo "Could not find $VARIANT"
    echo "build.sh <variant>"
    exit 1
fi

if [ -f "$PROPERTIES_FILE" ]; then
    if [ "$OSTYPE" = "msys" ]; then
        PYTHON="python"
    else
        PYTHON="/tools/python/bin/python"
    fi
    JSONTOOL="$PYTHON $SCRIPTS_DIR/buildfarm/utils/jsontool.py"

    builder=$($JSONTOOL -k properties.buildername $PROPERTIES_FILE)
    slavename=$($JSONTOOL -k properties.slavename $PROPERTIES_FILE)
    master=$($JSONTOOL -k properties.master $PROPERTIES_FILE)

    builddir=$(basename $PWD)
    branch=$(basename $HG_REPO)

    # Clobbering
    if [ -z "$CLOBBERER_URL" ]; then
        export CLOBBERER_URL="http://build.mozilla.org/clobberer"
    fi

    cd $SCRIPTS_DIR/../..
    python $SCRIPTS_DIR/clobberer/clobberer.py -s scripts -s $PROPERTIES_FILE \
        $CLOBBERER_URL $branch "$builder" $builddir $slavename $master

    # Purging
    cd $SCRIPTS_DIR/..
    python $SCRIPTS_DIR/buildfarm/maintenance/purge_builds.py \
        -s 4 -n info -n 'rel-*' -n $builddir
fi

python $SCRIPTS_DIR/buildfarm/utils/hgtool.py --tbox $HG_REPO src || exit 2

(cd src/js/src; autoconf-2.13 || autoconf2.13)

test -d objdir || mkdir objdir
cd objdir

OBJDIR=$PWD

echo OBJDIR is $OBJDIR

CONFIGURE_ARGS=$(cat $SPIDERDIR/$VARIANT)

if [ "$OSTYPE" = "linux-gnu" ]; then
    CONFIGURE_ARGS="$CONFIGURE_ARGS --with-ccache"
    UNAME_M=$(uname -m)
    MAKEFLAGS=-j4
    if [ "$UNAME_M" != "arm" ]; then
        export CC=/tools/gcc-4.5/bin/gcc
        export CXX=/tools/gcc-4.5/bin/g++
        if [ "$UNAME_M" = "x86_64" ]; then
            export LD_LIBRARY_PATH=/tools/gcc-4.5/lib64
        else
            export LD_LIBRARY_PATH=/tools/gcc-4.5/lib
        fi
    fi
fi

test -d nspr || mkdir nspr
(cd nspr
../../src/nsprpub/configure --prefix=$OBJDIR/dist --with-dist-prefix=$OBJDIR/dist --with-mozilla
make && make install
) || exit 2

test -d js || mkdir js

cd js
NSPR_CFLAGS=$($OBJDIR/dist/bin/nspr-config --cflags)
if [ "$OSTYPE" = "msys" ]; then
    NSPR_LIBS="$OBJDIR/dist/lib/plds4.lib $OBJDIR/dist/lib/plc4.lib $OBJDIR/dist/lib/nspr4.lib"
    export PATH="$OBJDIR/dist/lib:${PATH}"
else
    NSPR_LIBS=$($OBJDIR/dist/bin/nspr-config --libs)
fi
../../src/js/src/configure $CONFIGURE_ARGS --with-dist-dir=$OBJDIR/dist --prefix=$OBJDIR/dist --with-nspr-prefix=$OBJDIR/dist --with-nspr-cflags="$NSPR_CFLAGS" --with-nspr-libs="$NSPR_LIBS" || exit 2

make || exit 2
cp -p ../../src/build/unix/run-mozilla.sh $OBJDIR/dist/bin
make check || exit 1
