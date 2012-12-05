from mozdevice.devicemanagerSUT import DeviceManagerSUT

APP_INI_LOCATION = '/system/b2g/application.ini'

def main(device, doDebug=None):
    dm = None
    try:
        print "Connecting to: %s" % device
        dm = DeviceManagerSUT(device)
    except:
        print "ERROR: Unable to properly connect to SUT Port on device."
        return 1
    if doDebug:

        dm.debug = 5

    # No need for 300 second SUT socket timeouts here
    dm.default_timeout = 30

    if not dm.fileExists(APP_INI_LOCATION):
        print "ERROR: expected file (%s) not found" % APP_INI_LOCATION
        return 1

    fileContents = dm.catFile(APP_INI_LOCATION)
    if fileContents is None:
        print "ERROR: Unable to read file (%s)" % APP_INI_LOCATION

    print "Read of file (%s) follows" % APP_INI_LOCATION
    print "==========================="
    print fileContents
    # Success
    return 0

if __name__ == '__main__':
    import sys
    from optparse import OptionParser
    parser = OptionParser()
    parser.set_defaults(
        device=None,
        debug=False,
    )
    parser.add_option("-d", "--device", type="string", dest="device",
                      help="Device to connect to")
    parser.add_option("--debug", action="store_true", dest="debug",
                      help="Use debug devicemanager output")
    (options, args) = parser.parse_args()

    if not options.device:
        parser.error("argument --device is required.")

    if not options.device.startswith('panda'):
        parser.error("unexpected --device name")

    status = main(options.device, options.debug)
    sys.exit(status)
