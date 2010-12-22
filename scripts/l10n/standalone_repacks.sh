#!/bin/sh
set -e
set -x
# This ugly hack is a cross-platform (Linux/Mac/Windows+MSYS) way to get the
# absolute path to the directory containing this script
pushd `dirname $0` &>/dev/null
MY_DIR=$(pwd)
popd &>/dev/null
SCRIPTS_DIR="$MY_DIR/../../"
PYTHON="/tools/python/bin/python"
if [ ! -x $PYTHON ]; then
    PYTHON=python
fi
JSONTOOL="$PYTHON $SCRIPTS_DIR/buildfarm/utils/jsontool.py"
workdir=`pwd`

platform=$1
branchConfig=$2

releaseConfig=$($JSONTOOL -k properties.release_config $PROPERTIES_FILE)
releaseTag=$($JSONTOOL -k properties.script_repo_revision $PROPERTIES_FILE)
locales=$($JSONTOOL -k properties.locale $PROPERTIES_FILE)

if [ -z "$BUILDBOT_CONFIGS" ]; then
    export BUILDBOT_CONFIGS="http://hg.mozilla.org/build/buildbot-configs"
fi

LOCALE_OPT=
IFS=":"
for locale in $locales;
do
    LOCALE_OPT="$LOCALE_OPT --locale $locale"
done
unset IFS

cd $workdir

$PYTHON $MY_DIR/create-release-repacks.py -c $branchConfig -r $releaseConfig \
  -b $BUILDBOT_CONFIGS -t $releaseTag -p $platform \
  $LOCALE_OPT
