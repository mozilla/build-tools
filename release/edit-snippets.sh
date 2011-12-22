#!/bin/bash

snippetVar=$1; shift
changeTo=$1; shift
dirs=$@

if [[ -z "$snippetVar" || -z "$changeTo" || -z "$dirs" ]]; then
    echo "Usage: $0 from to dir [dir ...]"
    exit 1
fi

for dir in $dirs; do
    if [ ! -d $dir ]; then
        echo "Can't find dir '$dir', bailing..."
        exit 1
    fi
done

for dir in $dirs; do
    find $dir -type f -name "*.txt" -exec sed -i -c -e "s/^$snippetVar.*$/$snippetVar=$changeTo/" {} \;
done
