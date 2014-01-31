#!/bin/bash
set -e
set -x
pushd $(dirname $0)/../../ > /dev/null
SCRIPTS_DIR=$PWD
popd > /dev/null

SPIDERDIR=$SCRIPTS_DIR/scripts/spidermonkey_builds

if [ -z "$HG_REPO" ]; then
    export HG_REPO="https://hg.mozilla.org/integration/mozilla-inbound"
fi

function usage() {
  echo "Usage: $0 [-m mirror_url] [-b bundle_url] [-r revision] variant"
}

# It doesn't work to just pull from try. If you try to pull the full repo,
# it'll error out because it's too big. Even if you restrict to a particular
# revision, the pull is painfully slow (as in, it could take days) without
# --bundle and/or --mirror.
hgtool_args=()
while [ $# -gt 1 ]; do
    case "$1" in
        -m|--mirror)
            shift
            hgtool_args+=(--mirror "$1")
            shift
            ;;
        -b|--bundle)
            shift
            hgtool_args+=(--bundle "$1")
            shift
            ;;
        -r|--rev)
            shift
            hgtool_args+=(--clone-by-revision -r "$1")
            shift
            ;;
        *)
            echo "Invalid arguments" >&2
            usage
            exit 1
            ;;
    esac
done

VARIANT=$1
if [ ! -f "$SPIDERDIR/$VARIANT" ]; then
    echo "Could not find $VARIANT"
    usage
    exit 1
fi

PYTHON="python"
if [ -f "$PROPERTIES_FILE" ]; then
    JSONTOOL="$PYTHON $SCRIPTS_DIR/buildfarm/utils/jsontool.py"

    builder=$($JSONTOOL -k properties.buildername $PROPERTIES_FILE)
    slavename=$($JSONTOOL -k properties.slavename $PROPERTIES_FILE)
    master=$($JSONTOOL -k properties.master $PROPERTIES_FILE)

    builddir=$(basename $PWD)
    branch=$(basename $HG_REPO)

    # Clobbering
    if [ -z "$CLOBBERER_URL" ]; then
        export CLOBBERER_URL="http://clobberer.pvt.build.mozilla.org/index.php"
    fi

    cd $SCRIPTS_DIR/../..
    $PYTHON $SCRIPTS_DIR/clobberer/clobberer.py -s scripts \
        -s ${PROPERTIES_FILE##*/} \
        $CLOBBERER_URL $branch "$builder" $builddir $slavename $master || true

    # Purging
    cd $SCRIPTS_DIR/..
    $PYTHON $SCRIPTS_DIR/buildfarm/maintenance/purge_builds.py \
        -s 4 -n info -n 'rel-*' -n 'tb-rel-*' -n $builddir
fi

$PYTHON $SCRIPTS_DIR/buildfarm/utils/hgtool.py "${hgtool_args[@]}" $HG_REPO src || exit 2

(cd src/js/src; autoconf-2.13 || autoconf2.13)

TRY_OVERRIDE=src/js/src/config.try
if [ -r $TRY_OVERRIDE ]; then
  CONFIGURE_ARGS=$(cat $TRY_OVERRIDE)
else
  CONFIGURE_ARGS=$(cat $SPIDERDIR/$VARIANT)
fi

# Always do clobber builds. They're fast.
[ -d objdir ] && rm -rf objdir
mkdir objdir
cd objdir

OBJDIR=$PWD

echo OBJDIR is $OBJDIR

NSPR64=""
if [[ "$OSTYPE" == darwin* ]]; then
    NSPR64="--enable-64bit"
fi

if [ "$OSTYPE" = "linux-gnu" ]; then
    GCCDIR=/tools/gcc-4.7.2-0moz1
    CONFIGURE_ARGS="$CONFIGURE_ARGS --with-ccache"
    UNAME_M=$(uname -m)
    MAKEFLAGS=-j4
    if [ "$UNAME_M" != "arm" ]; then
        export CC=$GCCDIR/bin/gcc
        export CXX=$GCCDIR/bin/g++
        if [ "$UNAME_M" = "x86_64" ]; then
            export LD_LIBRARY_PATH=$GCCDIR/lib64
            NSPR64="--enable-64bit"
        else
            export LD_LIBRARY_PATH=$GCCDIR/lib
        fi
    fi
fi

test -d nspr || mkdir nspr
(cd nspr
../../src/nsprpub/configure --prefix=$OBJDIR/dist --with-dist-prefix=$OBJDIR/dist --with-mozilla $NSPR64
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

make -s -w -j4 || exit 2
cp -p ../../src/build/unix/run-mozilla.sh $OBJDIR/dist/bin

# The Root Analysis tests run in a special GC Zeal mode and disable ASLR to
# make tests reproducible.
COMMAND_PREFIX=''
if [[ "$VARIANT" = "rootanalysis" ]]; then
    export JS_GC_ZEAL=7

    # rootanalysis builds are currently only done on Linux, which should have
    # setarch, but just in case we enable them on another platform:
    if type setarch >/dev/null 2>&1; then
        COMMAND_PREFIX="setarch $(uname -m) -R "
    fi
fi
$COMMAND_PREFIX make check || exit 1
