#!/bin/bash

BASE_PATH=/home/ftp/pub/mozilla.org/firefox/tinderbox-builds
ARCHIVE_PATH=/home/ftp/pub/mozilla.org/firefox/nightly
DATE_BASE=$(date +%Y-%m-%d-%H)

DIRS=$(ls $BASE_PATH | grep 'mozilla.*debug$')
for dir in $DIRS
do
  branch=$(echo $dir | cut -d '-' -f1,2)
  builddir="$BASE_PATH/$dir"
  cd $builddir
  archivedir="$(ls -r | head -1)"
  if [ -n $archivedir ]; then
    if [ -d "$builddir/$archivedir" ]; then
      files="$(find $builddir/$archivedir/ -regex '.*\.\(dmg\|exe\|txt\|bz2\)')"
      for file in $files
      do
        echo "Found recent nightly: $file"
        backup=$(basename $file | sed s/en-US\./en-US.debug-/)
        if [ -e $file ]; then
          echo "Copying $file to $ARCHIVE_PATH/$DATE_BASE-$branch-debug/$backup"
          mkdir -p "$ARCHIVE_PATH/$DATE_BASE-$branch-debug/"
          cp -a $file "$ARCHIVE_PATH/$DATE_BASE-$branch-debug/$backup"
        fi;
      done
    else
      echo "skipping invalid dir"
    fi;
  fi;
done;
