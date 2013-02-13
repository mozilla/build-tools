#!/bin/bash
set -e -x
SCRIPTS_DIR="$(readlink -f $(dirname $0)/../..)"

if [ -z "$REVISION" ]; then
    export REVISION="default"
fi

if [ -z "$HG_REPO" ]; then
    export HG_REPO="http://hg.mozilla.org/mozilla-central"
fi

PYTHON="python"

if [ -f "$PROPERTIES_FILE" ]; then
    JSONTOOL="$PYTHON $SCRIPTS_DIR/buildfarm/utils/jsontool.py"

    builder=$($JSONTOOL -k properties.buildername $PROPERTIES_FILE)
    slavename=$($JSONTOOL -k properties.slavename $PROPERTIES_FILE)
    master=$($JSONTOOL -k properties.master $PROPERTIES_FILE)
    upload_host=$($JSONTOOL -k properties.upload_host $PROPERTIES_FILE)
    upload_user=$($JSONTOOL -k properties.upload_user $PROPERTIES_FILE)
    upload_sshkey=$($JSONTOOL -k properties.upload_sshkey $PROPERTIES_FILE)

    builddir=$(basename $(readlink -f .))
    branch=$(basename $HG_REPO)

    # Clobbering
    if [ -z "$CLOBBERER_URL" ]; then
        export CLOBBERER_URL="http://clobberer.pvt.build.mozilla.org/index.php"
    fi

    cd $SCRIPTS_DIR/../..
    $PYTHON $SCRIPTS_DIR/clobberer/clobberer.py -s scripts -s $(basename $PROPERTIES_FILE) \
        $CLOBBERER_URL $branch "$builder" $builddir $slavename $master

    # Purging
    cd $SCRIPTS_DIR/..
    $PYTHON $SCRIPTS_DIR/buildfarm/maintenance/purge_builds.py \
        -s 14 -n info -n 'rel-*' -n $builddir
fi

# Set up mock environment
echo "Setting up mock environment"
mock_mozilla -r mozilla-centos6-x86_64 --init || exit 2

# Copied from a linux x86-64 try-debug, modified slightly
mock_mozilla -v -r mozilla-centos6-x86_64 --install autoconf213 python zip \
  mozilla-python27-mercurial git ccache glibc-static libstdc++-static \
  perl-Test-Simple perl-Config-General gtk2-devel libnotify-devel \
  alsa-lib-devel libcurl-devel wireless-tools-devel libX11-devel libXt-devel \
  mesa-libGL-devel gnome-vfs2-devel GConf2-devel wget mpfr xorg-x11-font* \
  imake gcc45_0moz3 yasm pulseaudio-libs-devel pyxdg python-devel \
  python-jinja2 python-pygments sqlite-devel || exit 2

# Put our short revisions into the properties directory for consumption by buildbot.
if [ ! -d properties ]; then
    mkdir properties
fi

echo "Downloading/unpacking dxr build env"
rm -rf dxr-build-env
mkdir -p dxr-build-env
python /tools/tooltool.py -m $(dirname $0)/dxr.manifest -o --url http://runtime-binaries.pvt.build.mozilla.org/tooltool fetch
tar xf clang.tar.bz2 -C dxr-build-env || exit 2
tar xf dxr-build-env.tar.gz -C dxr-build-env || exit 2
# Expected layout of dxr-build-env:
# trilite -> source directory of dxr/trilite repository

MOCK_PATH=/usr/local/bin:$PWD/dxr-build-env/clang/bin:$PATH

echo "Checking out sources"
cd dxr-build-env

# Build and make DXR
# TODO: support dxr/dxr-stable here
DXR_REPO=http://hg.mozilla.org/projects/dxr
$PYTHON $SCRIPTS_DIR/buildfarm/utils/hgtool.py --rev $REVISION -b default $DXR_REPO dxr || exit 2

# Unpack trilite
mv trilite dxr/trilite

# Build DXR binary plugins
mock_mozilla -r mozilla-centos6-x86_64 --cwd=$PWD --shell --unpriv /bin/env \
  PATH=$MOCK_PATH CC=clang CXX=clang++ "make -C dxr"

# Pull the repository...
$PYTHON $SCRIPTS_DIR/buildfarm/utils/hgtool.py -b default $HG_REPO src || exit 2

# ... and record its revision
pushd src; GOT_REVISION=`hg parent --template={node} | cut -c1-12`; popd
echo "revision: $GOT_REVISION" > ../properties/revision
echo "got_revision: $GOT_REVISION" > ../properties/got_revision

# Create our config file
cp -f ../scripts/scripts/dxr/dxr.config .

echo "dxr.config:"
cat dxr.config

# Clean up the old build directories
rm -rf www; mkdir www
rm -rf objdir-mc-opt; mkdir objdir-mc-opt

echo "Starting build"
set +e
# XXX: compile-build hack
echo "ac_add_options --enable-stdcxx-compat" > src/.mozconfig
mock_mozilla -r mozilla-centos6-x86_64 --cwd=$PWD --shell --unpriv /bin/env \
  PATH=$MOCK_PATH LD_LIBRARY_PATH=$PWD/dxr/trilite \
  "dxr/dxr-build.py -j6 -f dxr.config -s -t $branch" 2>&1 \
  | grep -v 'Unprocessed kind'
retval=${PIPESTATUS[0]}

set -e
if [ $retval != 0 ]; then
    exit $retval
fi

fn=dxr-$branch.tar.gz

if [ -n "$upload_host" ]; then
    echo "Tarring up into $fn"
    tar zcf $fn www
    echo "Uploading"
    echo scp -i $upload_sshkey $fn $upload_user@$upload_host:/pub/mozilla.org/dxr/$fn
    scp -i $upload_sshkey $fn $upload_user@$upload_host:/pub/mozilla.org/dxr/$fn
fi
