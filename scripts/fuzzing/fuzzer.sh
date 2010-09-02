#!/bin/bash
set -e
eval `ssh-agent`
ssh-add ~/.ssh/ffxbld_dsa
trap "ssh-agent -k" EXIT

if [ -d fuzzing ]; then
    (cd fuzzing; hg pull; hg update -C)
else
    hg clone $HG_REPO
fi
python fuzzing/dom/automation/bot.py --remote-host "$FUZZ_REMOTE_HOST" --basedir "$FUZZ_BASE_DIR"
