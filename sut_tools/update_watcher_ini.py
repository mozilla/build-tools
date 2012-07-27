#!/usr/bin/env python

def main(tegra):
    import devicemanagerSUT
    destname = '/data/data/com.mozilla.watcher/files/watcher.ini'
    tmpname = '/mnt/sdcard/watcher.ini'
    data = '\r\n[watcher]\r\nPingTarget = bm-remote.build.mozilla.org\r\n'
    dm = devicemanagerSUT.DeviceManagerSUT(tegra, 20701)
    dm.verifySendCMD(['push %s %s\r\n' % (tmpname, len(data)), data], newline = False)
    dm.sendCMD(['exec su -c "dd if=%s of=%s"' % (tmpname, destname)])

if len(sys.argv[1:]) == 0:
    print "usage: %s [tegra-]### [...]" % sys.argv[0]
    sys.exit(1)

for tegra in sys.argv[1:]:
    if not tegra.lower().startswith('tegra-'):
        tegra = 'tegra-%s' % tegra
    main(tegra)
