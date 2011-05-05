#!/bin/sh
set -e
db=$1
sqlite3 $1 "delete from builds where last_build_time < strftime('%s', 'now', '-21 days') and buildername not like 'rel%';"
sqlite3 $1 "delete from clobber_times where lastclobber < strftime('%s', 'now', '-21 days');"
sqlite3 $1 "vacuum;"

