#!/usr/bin/python
import subprocess, re
def count_ctors(filename):
    proc = subprocess.Popen(['readelf', '-W', '-S', filename], stdout=subprocess.PIPE)

    for line in proc.stdout:
        f = line.split()
        if len(f) != 11:
            continue
        if f[1] == ".ctors" and f[2] == "PROGBITS":
            return int(f[5], 16) / int(f[10]) - 2;
        if f[1] == ".init_array" and f[2] == "PROGBITS":
            return int(f[5], 16) / int(f[10]);

if __name__ == '__main__':
    import sys
    for f in sys.argv[1:]:
        print "%s\t%s" % (count_ctors(f), f)
