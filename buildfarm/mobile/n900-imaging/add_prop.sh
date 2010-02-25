#!/bin/bash
test -f proprietary_files.txt || touch proprietary_files.txt
echo "$(openssl sha1 $1)" | tee -a proprietary_files.txt