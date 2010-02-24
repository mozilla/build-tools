#!/bin/bash
#
# This script pulls all the Mozilla-hosted Perl modules that the scripts in
# this directory require. It depends on the CVS and rsync binaries, and being 
# executed from the release directory of a build/tools clone.

DEFAULT_CVSROOT=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot"
CVS_MODULES="mozilla/tools/release/Bootstrap mozilla/tools/release/MozBuild mozilla/tools/patcher-configs"
HG_MODULES="lib/perl/Release"
REQUIRED_BINARIES="cvs rsync"

if [ -z $CVSROOT ]; then
    export CVSROOT=$DEFAULT_CVSROOT
fi

for b in $REQUIRED_BINARIES; do
    which $b &>/dev/null
    if [[ $? != 0 ]]; then
        echo "Could not find $b, exiting!"
        exit 1
    fi
done

for m in $CVS_MODULES; do
    dir=$(basename $m)
    if [ -e $dir ]; then
        echo "$dir already exists, skipping $m"
        continue
    fi
    cvs co -d $dir $m
done

for m in $HG_MODULES; do
    dir=$(basename $m)
    if [ -e $dir ]; then
        echo "$dir already exists, skipping $m"
        continue
    fi
    rsync -av ../$m ./
done
