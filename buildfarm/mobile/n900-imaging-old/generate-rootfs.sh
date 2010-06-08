#!/bin/sh
if [[ x"$1" == "x" || x"$2" == "x" ]] ; then
    echo "Usage: $0 <rootfsdir> <basename of image>"
    exit 1
fi
if [ ! $EUID -eq 0 ] ; then
    echo "$0 must be run as root"
    exit 1
fi
if [ ! -d $1 ] ; then
    echo "Specified root directory is not a directory"
    exit 1
fi
ROOT=$1
if [[ -f ${2}.ubi || -f ${2}.ubifs ]] ; then
    echo "I will not overwrite files\!"
    exit 1
fi
OUTPUT=$2

MKFS_UBIFS="./mkfs.ubifs"
UBINIZE="./ubinize"
echo "Using mkfs.ubifs: $MKFS_UBIFS and ubinize: $UBINIZE"
for i in .jffs2 .ubifs .ubi .ubi_jffs2 .ubifs_jffs2 ; do
	OUTPUT=`basename $OUTPUT $i`
done

echo "putting scripts into filesystem"
rsync -av rootfs/. ${ROOT}/.
echo "using $OUTPUT generated `date`" | tee ${ROOT}/image-ver

cat > ubi.cfg <<EOF
[rootfs]
mode=ubi
image=${OUTPUT}.ubifs
vol_id=0
vol_size=200MiB
vol_type=dynamic
vol_name=rootfs
vol_flags=autoresize
vol_alignment=1
EOF
echo "Generating ubifs filesystem"
$MKFS_UBIFS -m 2048 -e 129024 -c 2047 -r $ROOT ${OUTPUT}.ubifs
echo "Generating ubi image"
$UBINIZE -o ${OUTPUT}.ubi -p 128KiB -m 2048 -s 512 ubi.cfg
echo "All Done\!"