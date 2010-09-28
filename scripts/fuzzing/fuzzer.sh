#!/bin/bash
set -e
eval `ssh-agent`
ssh-add ~/.ssh/ffxbld_dsa
trap "ssh-agent -k" EXIT

SCRIPTS_DIR="$(dirname $0)/../.."

python $SCRIPTS_DIR/buildfarm/utils/hgtool.py $HG_REPO fuzzing

python fuzzing/dom/automation/bot.py --remote-host "$FUZZ_REMOTE_HOST" --basedir "$FUZZ_BASE_DIR"
