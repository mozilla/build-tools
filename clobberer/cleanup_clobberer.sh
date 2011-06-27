#!/bin/sh

CLEANUP_PASSWORD=sekrits
wget "http://build.mozilla.org/clobberer/cleanup.php?pass=$CLEANUP_PASSWORD" 2>/dev/null
