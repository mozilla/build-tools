#!/usr/bin/env python
import sut_lib
import sys

if __name__ == '__main__':
    if (len(sys.argv) != 2):
        print "usage: tegra_checkstalled.py <tegra name>"
        sys.exit(1)

    if sut_lib.checkStalled(sys.argv[1]) in (1, 2, 3):
        sys.exit(0)

    print "Unknown Error"
    sys.exit(1)
