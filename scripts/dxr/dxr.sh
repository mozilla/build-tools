#!/bin/bash
set -e
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

mock_mozilla -r mozilla-centos6-x86_64 --install mpfr autoconf213 zip pyxdg gtk2-devel libnotify-devel alsa-lib-devel libcurl-devel wireless-tools-devel libX11-devel libXt-devel mesa-libGL-devel python-devel mozilla-python27-mercurial || exit 2
# Put our short revisions into the properties directory for consumption by buildbot.
if [ ! -d properties ]; then
    mkdir properties
fi

echo "Downloading/unpacking dxr build env"
rm -rf dxr-build-env
mkdir -p dxr-build-env
python /tools/tooltool.py -m $(dirname $0)/dxr.manifest -o --url http://runtime-binaries.pvt.build.mozilla.org/tooltool fetch
(cd dxr-build-env; tar xf ../dxr-build-env-r8.tar.gz) || exit 2

echo "Checking out sources"
cd dxr-build-env
$PYTHON $SCRIPTS_DIR/buildfarm/utils/hgtool.py --rev $REVISION -b default $HG_REPO src || exit 2

# TODO: support dxr/dxr-stable here
$PYTHON $SCRIPTS_DIR/buildfarm/utils/hgtool.py --rev $REVISION -b default http://hg.mozilla.org/projects/dxr dxr || exit 2

pushd src; GOT_REVISION=`hg parent --template={node} | cut -c1-12`; popd
echo "revision: $GOT_REVISION" > ../properties/revision
echo "got_revision: $GOT_REVISION" > ../properties/got_revision

# Create our config file
sed "s?PWD?$PWD?g" dxr.config.in | sed "s?^sourcedir=.*?sourcedir=$PWD/src?" | sed "s?NB_JOBS?6?g" > dxr.config

echo "dxr.config:"
cat dxr.config

rm -rf www; mkdir www
rm -rf objdir-mc-opt; mkdir objdir-mc-opt

echo "Starting build"
set +e
mock_mozilla -r mozilla-centos6-x86_64 --cwd=$PWD --shell --unpriv /bin/env PATH=/usr/local/bin:$PATH make
mock_mozilla -r mozilla-centos6-x86_64 --cwd=$PWD --shell --unpriv /bin/env PATH=/usr/local/bin:$PATH ./build.sh 2>&1 | grep -v '^Unprocessed kind'
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
