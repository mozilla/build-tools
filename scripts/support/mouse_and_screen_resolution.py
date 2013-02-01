#! /usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

#
# Script name:   mouse_and_screen_resolution.py
# Purpose:       Sets mouse position and screen resolution for Windows 7 32-bit slaves
# Author(s):     Zambrano Gasparnian, Armen <armenzg@mozilla.com>
# Target:        Python 2.5
#
from optparse import OptionParser
try:
    import json
except:
    import simplejson as json
import os
import sys
import urllib2
import win32api
import win32con
import pywintypes
import platform
import time
from win32api import GetSystemMetrics

default_screen_resolution = {"x": 1024, "y": 768}
default_mouse_position = {"x": 1010, "y": 10}


def wfetch(url, retries=5):
    while retries >= 0:
        try:
            return urllib2.urlopen(url).read()
        except urllib2.HTTPError, e:
            print("Failed to fetch '%s': %s" % (url, str(e)))
            if retries == 0:
                raise
            print("Retrying...")
            retries = retries - 1
        except urllib2.URLError, e:
            print("Failed to fetch '%s': %s" % (url, str(e)))
            if retries == 0:
                raise
            print("Retrying...")
            retries = retries - 1
        time.sleep(60)
    raise Exception("Could not fetch url '%s'" % url)


def main():
    '''
    We load the configuration file from:
    http://hg.mozilla.org/mozilla-central/raw-file/default/build/machine-configuration.json
    '''
    parser = OptionParser()
    parser.add_option(
        "--configuration-url", dest="configuration_url", type="string",
        help="It indicates from where to download the configuration file.")
    (options, args) = parser.parse_args()

    if options.configuration_url == None:
        print "You need to specify --configuration-url."
        return 1

    if not (platform.version().startswith('6.1.760') and not 'PROGRAMFILES(X86)' in os.environ):
        # We only want to run this for Windows 7 32-bit
        print "INFO: This script was written to be used with Windows 7 32-bit machines."
        return 0

    try:
        conf_dict = json.loads(wfetch(options.configuration_url))
        new_screen_resolution = conf_dict["win7"]["screen_resolution"]
        new_mouse_position = conf_dict["win7"]["mouse_position"]
    except urllib2.HTTPError, e:
        print "This branch does not seem to have the configuration file %s" % str(e)
        print "Let's fail over to 1024x768."
        new_screen_resolution = default_screen_resolution
        new_mouse_position = default_mouse_position
    except urllib2.URLError, e:
        print "INFRA-ERROR: We couldn't reach hg.mozilla.org: %s" % str(e)
        return 1
    except Exception, e:
        print "ERROR: We were not expecting any more exceptions: %s" % str(e)
        return 1

    current_screen_resolution = queryScreenResolution()
    print "Screen resolution (current): (%(x)s, %(y)s)" % (current_screen_resolution)

    if current_screen_resolution == new_screen_resolution:
        print "No need to change the screen resolution."
    else:
        print "Changing the screen resolution..."
        try:
            changeScreenResolution(new_screen_resolution)
        except Exception, e:
            print "INFRA-ERROR: We have attempted to change the screen resolution but " + \
                  "something went wrong: %s" % str(e)
            return 1
        time.sleep(5)  # just in case
        current_screen_resolution = queryScreenResolution()
        print "Screen resolution (new): (%(x)s, %(y)s)" % current_screen_resolution

    print "Mouse position (current): (%(x)s, %(y)s)" % (queryMousePosition())
    win32api.SetCursorPos((new_mouse_position["x"], new_mouse_position["y"]))
    current_mouse_position = queryMousePosition()
    print "Mouse position (new): (%(x)s, %(y)s)" % (current_mouse_position)

    if current_screen_resolution != new_screen_resolution or current_mouse_position != new_mouse_position:
        print "INFRA-ERROR: The new screen resolution or mouse positions are not what we expected"
        return 1
    else:
        return 0


def queryMousePosition():
    pos = win32api.GetCursorPos()
    return {"x": pos[0], "y": pos[1]}


def queryScreenResolution():
    return {"x": GetSystemMetrics(0), "y": GetSystemMetrics(1)}


def queryScreenFrequency():
    try:
        p = win32api.EnumDisplaySettings(None, win32con.ENUM_CURRENT_SETTINGS)
        return p.DisplayFrequency
    except Exception, e:
        print "INFRA-ERROR: We were expecting to get the screen frequency instead we " + \
              "got this exception => %s" % str(e)
        return 1


def changeScreenResolution(new):
    # Set new screen resolution
    display_modes = {}
    n = 0
    while True:
        try:
            devmode = win32api.EnumDisplaySettings(None, n)
        except pywintypes.error:
            break
        else:
            key = (
                devmode.BitsPerPel,
                devmode.PelsWidth,
                devmode.PelsHeight,
                devmode.DisplayFrequency
            )
            display_modes[key] = devmode
            n += 1
    mode_required = (32, new["x"], new["y"], queryScreenFrequency())
    devmode = display_modes[mode_required]
    win32api.ChangeDisplaySettings(devmode, 0)

if __name__ == '__main__':
    sys.exit(main())
