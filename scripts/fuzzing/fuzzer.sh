#!/bin/bash
set -e
eval `ssh-agent`
ssh-add ~/.ssh/ffxbld_dsa
trap "ssh-agent -k" EXIT

SCRIPTS_DIR="$(dirname $0)/../.."

# Call the Python 2.7 package in Win32 machines prior to bug 780291 getting fixed.
if [ $OS = "Windows_NT" ] && [ -e "/d/mozilla-build/python27/python.exe" ]; then
    PYBIN="/d/mozilla-build/python27/python.exe"
else
    PYBIN="python"
fi

$PYBIN $SCRIPTS_DIR/buildfarm/utils/hgtool.py $HG_REPO fuzzing
$PYBIN fuzzing/bot.py --remote-host "$FUZZ_REMOTE_HOST" --basedir "$FUZZ_BASE_DIR"
