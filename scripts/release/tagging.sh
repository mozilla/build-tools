#!/bin/sh
set -e
MY_DIR=$(dirname $(readlink -f $0))
SCRIPTS_DIR="$MY_DIR/../../"
PYTHON="/tools/python/bin/python"
JSONTOOL="$PYTHON $SCRIPTS_DIR/buildfarm/utils/jsontool.py"
workdir=`pwd`

releaseConfig=$($JSONTOOL -k properties.release_config $PROPERTIES_FILE)
releaseTag=$($JSONTOOL -k properties.script_repo_revision $PROPERTIES_FILE)
# Clobberer requires the short name of the branch
branch=$(basename $($JSONTOOL -k properties.branch $PROPERTIES_FILE))
builder=$($JSONTOOL -k properties.buildername $PROPERTIES_FILE)
slavebuilddir=$($JSONTOOL -k properties.slavebuilddir $PROPERTIES_FILE)
slavename=$($JSONTOOL -k properties.slavename $PROPERTIES_FILE)
master=$($JSONTOOL -k properties.master $PROPERTIES_FILE)

if [ -z "$BUILDBOT_CONFIGS" ]; then
    export BUILDBOT_CONFIGS="http://hg.mozilla.org/build/buildbot-configs"
fi
if [ -z "$CLOBBERER_URL" ]; then
    export CLOBBERER_URL="http://build.mozilla.org/clobberer"
fi

echo "Calling clobberer: $PYTHON $SCRIPTS_DIR/clobberer/clobberer.py -s build $CLOBBERER_URL $branch $builder $slavebuilddir $slavename $master"
cd $SCRIPTS_DIR/../../..
$PYTHON $SCRIPTS_DIR/clobberer/clobberer.py -s build $CLOBBERER_URL $branch $builder $slavebuilddir $slavename $master
cd $workdir

echo "Calling tag-release.py: $PYTHON tag-release.py -c $releaseConfig -b $BUILDBOT_CONFIGS -t $releaseTag"
$PYTHON $MY_DIR/tag-release.py -c $releaseConfig -b $BUILDBOT_CONFIGS -t $releaseTag || exit 2
