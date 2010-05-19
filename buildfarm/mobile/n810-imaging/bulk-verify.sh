#!/bin/bash

while true ; do
    echo Remove ALL MicroSD card from MicroSD card readers
    echo Remove ALL MicroSD card readers from computer
    echo -n Press enter when this is done
    read
    sync
    echo Insert ONE MicroSD card reader with card
    STATUS=1
    while [ $STATUS -eq 1 ] ; do
        ls -l /dev/sd?? | grep floppy &> /dev/null
        STATUS=$?
        sleep 1
    done
    while true ; do 
        STATUS=1
        while [ $STATUS -ne 0 ] ; do
            ls -l /dev/sd?? | grep floppy &> /dev/null
            STATUS=$?
            sleep 1
        done
        HOSTNAME=""
        while [ x"$HOSTNAME" == "x" ] ; do
            echo -n 'Type full hostname without domain (e.g. maemo-n810-000): '
            read HOSTNAME 
        done
        ./moz-verify.sh $HOSTNAME &> verify-debug.log
        if [ $? -ne 0 ] ; then
            echo '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
            printf "\n\n\n\a\n\n\n THIS IS AN INVALID CARD"
            echo '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
            cat verify-debug.log
        else
            echo This is a valid card.  Insert this card into $HOSTNAME
        fi
        echo Remove MicroSD card reader with card
        STATUS=0
        while [ $STATUS -eq 0 ] ; do
            ls -l /dev/sd?? | grep floppy &> /dev/null
            STATUS=$?
            sleep 1
        done
        echo press CTRL+C to quit or Insert MicroSD card into MicroSD card reader
        echo then plug in MicroSD card reader with MicroSD card into computer
    done
done
