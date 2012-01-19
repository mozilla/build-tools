#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
import sut_lib

if len(sut_lib.tegras) == 0:
    print "error: The tegras.json data file appears to be empty or not found."
    sys.exit(2)

if len(sys.argv[1:]) == 0:
    print "usage: %s [tegra-]### [...]" % sys.argv[0]
    sys.exit(1)

for tegra in sys.argv[1:]:
    if not tegra.lower().startswith('tegra-'):
        tegra = 'tegra-%s' % tegra

    sut_lib.reboot_tegra(tegra, debug=True)

