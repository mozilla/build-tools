#!/bin/sh

STANDALONE_FILE="/builds/standalone.txt"
HOSTNAME=`hostname`
FQDN="$HOSTNAME.build.mozilla.org"
MESSAGE=""
STATUS=0
EXPECTED_NUM_BUILDBOT_PROCS=1
LOW_MEM_THRESHOLD=1024
LOW_DISK_THRESHOLD=512

# Respect the no-go file
if [ -f $STANDALONE_FILE ] ; then
   echo "$HOSTNAME standalone.txt exists: `cat $STANDALONE_FILE`"
   exit 1
fi

# Check hostname, make sure it matches ip
if [ $HOSTNAME == "maemo-n810-ref" ] ; then
	MESSAGE="${MESSAGE}$HOSTNAME is named maemo-n810-ref!
"
	STATUS=`expr $STATUS + 1`
else
	DNS_IP=`nslookup $FQDN | tail -1 | cut -d' ' -f 3`
	MY_IP=`ifconfig wlan0 | grep inet | sed -e 's/^[^:]*:\([0-9\.]*\) .*$/\1/'`
	if [ $MY_IP != $DNS_IP ] ; then
		MESSAGE="${MESSAGE}My ip $MY_IP different from DNS $FQDN: $DNS_IP!
"
		STATUS=`expr $STATUS + 1`
	fi
fi

# Up for more than a day?
echo $UPTIME | grep 'day' >/dev/null 2>&1
if [ $? -eq 0 ] ; then
	MESSAGE="$MESSAGE$HOSTNAME has been up over a day.
"
	STATUS=`expr $STATUS + 1`
fi

# Buildbot running?
NUMPROCS=`ps -ef | grep buildbot | grep -v grep | wc -l`
if [ $NUMPROCS -ne $EXPECTED_NUM_BUILDBOT_PROCS ] ; then
	MESSAGE="$MESSAGE$HOSTNAME running $NUMPROCS copies of buildbot (expected $EXPECTEDNUMPROCS)
" 
	STATUS=`expr $STATUS + 1`
fi

# Plugged in?
POWER=`cat /sys/power/sleep_while_idle`
if [ $POWER -gt 0 ] ; then
	MESSAGE="${MESSAGE}$HOSTNAME is unplugged.
"
	STATUS=`expr $STATUS + 1`
fi

# Has swap?
TOTALSWAP=`free | grep Swap | sed -e 's/  */ /g' | cut -d' ' -f3`
if [ $TOTALSWAP -ne 131196 ] ; then
	MESSAGE="$MESSAGE$HOSTNAME unexpected total swap $TOTALSWAP!
"
	STATUS=`expr $STATUS + 1`
fi

# Low memory?
FREEMEM=`free | grep Total | sed -e 's/  */ /g' | cut -d' ' -f4`
if [ $FREEMEM -lt $LOW_MEM_THRESHOLD ] ; then
	MESSAGE="$MESSAGE$HOSTNAME low memory $FREEMEM!
"
	STATUS=`expr $STATUS + 1`
fi

# Read-only filesystems?
TMPFILE="tmp.$$"
TMPDIRS="/var/log /media/mmc2"
for dir in $TMPDIRS; do
	ERRORS=0
	touch $dir/$TMPFILE
	ERRORS=$?
	if [ $ERRORS -eq 0 ] ; then
		rm -f $dir/$TMPFILE
		ERRORS=$?
	fi
	if [ $ERRORS -ne 0 ] ; then
		MESSAGE="$MESSAGE$HOSTNAME i/o error in $dir!
"
		STATUS=`expr $STATUS + 1`
	fi
done

for FS in /dev/mmcblk0p1 /dev/mmcblk1p2 ; do
	KBFREE=`df -k $FS | tail -1 | sed -e 's/  */ /g' | cut -d' ' -f4`
	if [ $KBFREE -lt $LOW_DISK_THRESHOLD ] ; then
		MESSAGE="$MESSAGE$HOSTNAME low disk on $FS: $KBFREE kb!
"
		STATUS=`expr $STATUS + 1`
	fi
done




if [ ".$MESSAGE" != "." ] ; then
	echo $MESSAGE
fi
exit $STATUS
