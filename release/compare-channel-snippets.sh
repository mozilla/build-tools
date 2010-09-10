#!/bin/bash

adir=`readlink -f $1`
achannel=$2
bdir=`readlink -f $3`
bchannel=$4
prettyadir=`basename $adir`
prettybdir=`basename $bdir`
ret=0

if [[ -z "$adir" || -z "$achannel" || -z "$bdir" || -z "$bchannel" ]]; then
    echo "Usage: $0 first-snippet-dir channel second-snippet-dir channel"
    exit 1
fi

pushd $adir >/dev/null
for asnippet in `find . -type f -iwholename "*/$achannel/*"`; do
    asnippet=${asnippet#./}
    bsnippet=`echo $asnippet | sed -e "s/$achannel/$bchannel/"`
    if [[ ! -e "$bdir/$bsnippet" ]]; then
        echo "WARN: $prettyadir/$asnippet exists"
        echo "  but $prettybdir/$bsnippet doesn't"
        continue
    fi
    diff -au $adir/$asnippet $bdir/$bsnippet
    if [[ $? != 0 ]]; then
        ret=1
    fi
done
popd $adir >/dev/null
pushd $bdir >/dev/null
for bsnippet in `find . -type f -iwholename "*/$bchannel/*"`; do
    bsnippet=${bsnippet#./}
    asnippet=`echo $bsnippet | sed -e "s/$bchannel/$achannel/"`
    if [[ ! -e "$adir/$asnippet" ]]; then
        echo "WARN: $prettybdir/$bsnippet exists"
        echo "  but $prettyadir/$asnippet doesn't"
    fi
    # No diffing happens here because we've already compare all comparable
    # files in the first loop
done
popd $bdir >/dev/null

exit $ret
