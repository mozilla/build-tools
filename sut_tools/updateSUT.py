import urllib2
import sys
import time
import devicemanagerSUT as devicemanager

# Constants
target_version = "1.07"
apkfilename = "sutAgentAndroid.apk"

def main(deviceIP):
    dm = connect(deviceIP)
    ver = version(dm)

    if ver != "SUTAgentAndroid Version %s" % target_version:
        print "INFO: updateSUT.py: We're going to try to install SUTAgentAndroid Version %s" % target_version
        try:
             data = download_apk()
        except e:
             print "ERROR: updateSUT.py: We have failed to retrieve the SUT Agent. %s" % e.reason
             return 5
        dm.sendCMD(['push /mnt/sdcard/%s %s\r\n' % (apkfilename, str(len(data))), data], newline=False)
        dm.debug = 5
        dm.sendCMD(['updt com.mozilla.SUTAgentAndroid /mnt/sdcard/%s' % apkfilename])
        # XXX devicemanager.py might need to close the sockets so we won't need these 2 steps
        if dm._sock:
            dm._sock.close()
        dm._sock = None
        dm = None
        ver = None
        tries = 0
        while tries < 5:
            try:
                dm = connect(deviceIP, sleep=90)
                break
            except:
                tries += 1
                print "WARNING: updateSUT.py: We have tried to connect %s time(s) after trying to update." % tries

        try:
            ver = version(dm)
        except e:
            print "ERROR: updateSUT.py: We should have been able to get the version"
            print "ERROR: updateSUT.py: %s" % e
            return 5

        if ver != None and ver != "SUTAgentAndroid Version %s" % target_version:
            print "ERROR: updateSUT.py: We should have had the %s version but instead we have %s" % \
                  (target_version, ver)
            return 5
        elif ver != None:
            print "INFO: updateSUT.py: We're now running %s" % ver
            return 0
        else:
            print "ERROR: updateSUT.py: We should have been able to connect and determine the version."
            return 5
    else:
        # The SUT Agent was already up-to-date
        return 0

def connect(deviceIP, sleep=None):
    if sleep:
        print "INFO: updateSUT.py: We're going to sleep for 90 seconds"
        time.sleep(90)

    print "INFO: updateSUT.py: Connecting to: " + deviceIP
    return devicemanager.DeviceManagerSUT(deviceIP)

def version(dm):
    ver = dm.sendCMD(['ver']).split("\n")[0]
    print "INFO: updateSUT.py: We're running %s" % ver
    return ver

def download_apk():
    url = 'http://build.mozilla.org/talos/mobile/sutAgentAndroid.%s.apk' % target_version
    print "INFO: updateSUT.py: We're downloading the apk: %s" % url
    req = urllib2.Request(url)
    try:
        f = urllib2.urlopen(req)
    except URLError, e:
        raise Exception("ERROR: updateSUT.py: code: %s; reason: %s" % i(e.code, e.reason))

    local_file = open(apkfilename, 'wb')
    local_file.write(f.read())
    local_file.close()
    f = open(apkfilename, 'rb')
    data = f.read()
    f.close()
    return data

if __name__ == '__main__':
    if (len(sys.argv) <> 2):
        print "usage: updateSUT.py <ip address>"
        sys.exit(1)

    sys.exit(main(sys.argv[1]))
