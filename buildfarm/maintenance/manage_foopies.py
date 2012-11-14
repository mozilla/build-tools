#!/usr/bin/env python
import foopy_fabric
from fabric.api import env
from fabric.context_managers import settings


def run_action_on_foopy(action, foopy):
    try:
        action_func = getattr(foopy_fabric, action)
        with settings(host_string="%s.build.mozilla.org" % foopy):
            action_func(foopy)
            return True
    except:
        import traceback
        print "Failed to run", action, "on", foopy
        print traceback.format_exc()
        return False

if __name__ == '__main__':
    from optparse import OptionParser
    try:
        import simplejson as json
    except:
        import json
    
    parser = OptionParser("""%%prog [options] action [action ...]""")
    
    parser.set_defaults(
        hosts=[],
        )
    parser.add_option("-f", "--devices-file", dest="devices_file", help="list/url of devices.json")
    parser.add_option("-H", "--host", dest="hosts", action="append")

    options, actions = parser.parse_args()

    if not options.devices_file:
        parser.error("devices-file is required")

    if not actions:
        parser.error("at least one action is required")

    all_devices = json.load(urllib.urlopen(options.devices_file))
    # Extract foopies from devices
    all_foopies = [all_devices[x]['foopy'] for x in all_devices
                                           if all_devices[x].has_key('foopy')]
    # Use set to trim dupes
    all_foopies = set(all_foopies) - set(["None"])
    # For sanity when using -H all, we revert to list and sort
    all_foopies = [x for x in all_foopies]
    all_foopies.sort()
    
    selected_foopies = []
    for f in all_foopies:
        if f in options.hosts:
            selected_foopies.append(f)
        elif 'all' in options.hosts:
            selected_foopies.append(f)
    
    if len(selected_foopies) == 0:
        parser.error("You need to specify a foopy via -H")
    
    env.user = 'cltbld'
    
    for action in actions:
        for foopy in selected_foopies:
            run_action_on_foopy(action, foopy)
