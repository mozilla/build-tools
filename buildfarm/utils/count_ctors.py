#!/usr/bin/python
import subprocess, re
def count_ctors(filename):
    proc = subprocess.Popen(['readelf', '-W', '-S', filename], stdout=subprocess.PIPE)

    for line in proc.stdout:
        m = re.search("\.ctors\s+PROGBITS\s+[0-9a-f]+\s+[0-9a-f]+\s+([0-9a-f]+)", line)
        if m:
            return int(m.group(1), 16)

if __name__ == '__main__':
    import sys
    for f in sys.argv[1:]:
        print "%s\t%s" % (count_ctors(f), f)
