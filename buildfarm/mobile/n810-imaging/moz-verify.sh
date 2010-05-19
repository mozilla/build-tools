#!/bin/bash
UNITNAME=$1
RSYNC=rsync2

function info {
  echo "INFO: $1"
}

function warn {
  echo "WARN: $1"
}

function error {
  echo "ERROR!($SDDEV): $1"
  if [[ x"$MOUNT" != "x" ]] ; then
    if [[ `mount | grep $MOUNT` ]] ; then
      echo "This card is defective! Imaging attempted `date`" > ${MOUNT}/sentinel
      echo "Copying imaging log to device"
      if [[ -f $LOGFILE ]] ; then
          cp $LOGFILE ${MOUNT}/imglog
      fi
    fi
  fi
  exit 1
}

function find_card {
    cards=$(ls -l /dev/sd?1 | grep floppy | cut -f9 -d ' ')
    readers=$(ls -l /dev/sd? | grep floppy | cut -f9 -d ' ')
    if [ x"$cards" == "x" ] ; then
        error "There are no sd cards in the computer"
    fi
    cardcount=$(echo $cards | wc -w)
    readercount=$(echo $readers | wc -w)
    if [ $cardcount -gt 1 ] ; then
        error "You have too many sd cards in the computer"
    elif [ $readercount -gt 1 ] ; then
        error "You have an empty sd card reader in the computer"
    else
        info "Found $CARD"
        CARD=$cards
    fi
}

function verify_card {
    info "Verifiying $CARD"
    fsck -n $CARD &> /dev/null
    if [ $? -eq 0 ] ; then
        info "fsck ok"
    else
        error "this fscking failed"
    fi
    mkdir -p $MOUNT
    mount $CARD $MOUNT || error "Unable to mount this card"
    echo $UNITNAME > ${MOUNT}/etc/hostname
    if [ $? -ne 0 ] ; then
        error "could not set hostname"
    else
        info "set hostname to $UNITNAME"
    fi
    if [ -f $MOUNT/sentinel ] ; then
      error "This card has a sentinel, signaling that something went wrong in imaging"
    else
      info "There is correctly no Sentinel"
    fi
    if [ ! -f $MOUNT/img-success ] ; then
      error "This card did not have the imaging process complete successfully"
    else
      info "Imaging was completed successfully"
    fi
}

function eject {
  info "Unmounting"
  sync
  STATUS=0
  while [ $STATUS -eq 0 ] ; do
    for i in `mount | cut -f1 -d ' ' | grep $CARD` ; do
      umount $i &> /dev/null || warn "could not umount $i"
    done
    mount | grep $CARD > /dev/null
    STATUS=$?
  done
}

if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
fi
if [[ "x$1" == "x" ]] ; then
  error "Usage: moz-verify.sh <sd card dev> <unit name>"
else
  MOUNT='verify'
  find_card
  eject
  verify_card
  eject
  sleep 2
  rm -rf $MOUNT
  info "Success on $CARD"
  rmdir $MOUNT &> /dev/null
  exit 0
fi
