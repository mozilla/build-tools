#!/usr/bin/env python

#
# Assumes Python 2.6
#

import os, sys
from sut_lib import reboot_tegra

for tegra in sys.argv[1:]:
    if not tegra.lower().startswith('tegra-'):
        tegra = 'tegra-%s' % tegra

    reboot_tegra(tegra, debug=True)
else:
    print "usage: %s [tegra-]### [...]" % sys.argv[0]
    sys.exit(1)

