#!/bin/bash
# Useful for finding out which devices: find /dev | grep "/dev/sd.[0-9]"
if [ x"$1" == "x" ] ; then
    ROOTFSDIR='moz-n810-v2'
else
    ROOTFSDIR=$1
fi

clean_exit () {
    for i in ${PIDS[@]} ; do
        ps | cut -f1 -d ' ' | grep $i &> /dev/null
        if [ $? -eq 0 ] ; then
            kill $i
        fi
    done
    echo "Success on 0 out of $COUNT devices"
}

trap clean_exit SIGHUP SIGINT SIGTERM

COUNT=0
for i in `ls -l /dev/sd? | grep floppy | sed 's/^.* //'` ; do
  BATCH='yes' ./moz-image.sh $ROOTFSDIR $i maemo-n810-NNN &
  DEVNODES[COUNT]=$i
  PIDS[COUNT]=$!
  COUNT=$(($COUNT + 1))
done

spin[0]='\'
spin[1]='|'
spin[2]='/'
spin[3]='-'
i=0
while true ; do
    if [ `jobs -r | wc -l` -gt 0 ] ; then
        sleep 1
        printf "\b%s" ${spin[i]}
        i=$(((i + 1) % 4))
    else
        break
    fi
    printf "\b"
done

SUCCESS=0
for node in ${DEVNODES[@]} ; do
    grep "Success on" debug-$(basename $node).log &> /dev/null
    if [ $? -eq 0 ] ; then
        SUCCESS=$(($SUCCESS + 1))
        rm debug-$(basename $node).log
    else
        echo
        echo "ERROR: Imaging failed. Relevant debug log debug-$(basename $node).log"
    fi
done

echo "Success on $SUCCESS of $COUNT devices"
echo "Done"
