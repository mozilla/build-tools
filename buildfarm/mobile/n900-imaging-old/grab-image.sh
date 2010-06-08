#!/bin/bash
HOST=$1
TARGET_ROOTFS=$2
TARGET_HOME="${TARGET_ROOTFS}-home"
if [[ $EUID != 0 ]] ; then
    echo "Script must be run as root"
    exit 1
fi
if [[ x"$HOST" == "x" || \
    x"$TARGET_ROOTFS" == "x" || \
    x"$TARGET_HOME" == "x" ]] ; then
    echo "Usage: $0 <host> <target>"
    exit 1
fi
echo "Host: $HOST"
echo "Target (rootfs): $TARGET_ROOTFS"
echo "Target (home): $TARGET_HOME"

remotecmd (){
    ssh root@${HOST} $@
}
remotecmd umount /floppy
remotecmd mount -t ubifs ubi0:rootfs /floppy
mkdir -p $TARGET_ROOTFS $TARGET_HOME
echo "RSYNC RootFS"
rsync -av root@${HOST}:/floppy/. $TARGET_ROOTFS
echo "RSYNC Home"
rsync -av root@${HOST}:/home/. $TARGET_HOME
echo "All Done!"
echo -n "You'd run sudo ./generate-rootfs.sh $TARGET_ROOTFS to create"
echo "a rootfs image for the device"
echo 
echo "You are going to have to create the tarball yourself"
