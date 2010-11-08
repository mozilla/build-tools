#!/bin/bash
# Usage: %prog platform

# Script to pull down the latest jetpack sdk tarball, unpack it, and run its tests against the 
# executable of whatever valid platform is passed.

set -e
JETPACK_TARBALL="jetpack.tar.bz2"
BASE_PATH=$(pwd)
 # handling for each platform's executable path
if [ "$1" == 'linux' -o "$1" == 'linux64' ]; then
  APP_PATH=$BASE_PATH/firefox/firefox
elif [ "$1" == 'macosx' -o "$1" == 'macosx64' ]; then
  APP_PATH=$(find $BASE_PATH -maxdepth 1 -type d -name '*.app')
elif [ "$1" == 'win32' ]; then
  APP_PATH=$BASE_PATH/firefox/firefox.exe
  # The --exclude=*.app is here to avoid extracting a
  # symlink on win32 that is only relevant to OS X.
  # It would be nice if we could just tell tar to
  # ignore symlinks...
  UNTAR_ARGS=--exclude=*.app
else
  echo "$1 is not a valid platform."
  exit 1
fi

if [ ! -e "$APP_PATH" ]; then
  echo "The location \"$APP_PATH\" does not exist"
  exit 1
fi

if [ ! -d "./jetpack" ]; then
  echo "No jetpack directory present!  Cannot run test suite."
  exit 1
fi

# Set up for running jetpack
cd "./jetpack"
# Download jetpack-latest tarball
wget -i "jetpack-location.txt" -O $JETPACK_TARBALL
tar -xvf $JETPACK_TARBALL $UNTAR_ARGS
# Find the sdk dir to run tests in
SDK_DIR=$(ls . | grep 'jetpack-sdk*')
if [ -d $SDK_DIR ]; then
  cd $SDK_DIR
  python bin/cfx testall -a firefox -b $APP_PATH
else
  echo "SDK_DIR is either missing or invalid."
  exit 1
fi
