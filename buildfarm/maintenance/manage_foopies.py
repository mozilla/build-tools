#!/usr/bin/env python
import foopy_fabric
from fabric.api import env
from fabric.context_managers import settings
from fabric.colors import red
from Crypto.Random import atfork

FAIL = red('[FAIL]')

def run_action_on_foopy(action, foopy):
    atfork()
    try:
        action_func = getattr(foopy_fabric, action)
        with settings(host_string="%s.build.mozilla.org" % foopy):
            action_func(foopy)
            return True
    except AttributeError:
        print FAIL, "[%s] %s action is not defined." % (foopy, action)
        return False
    except:
        import traceback
        print "Failed to run", action, "on", foopy
        print traceback.format_exc()
        return False

if __name__ == '__main__':
    from optparse import OptionParser
    import sys
    import urllib
    try:
        import simplejson as json
    except:
        import json
    
    parser = OptionParser("""%%prog [options] action [action ...]""")
    
    parser.set_defaults(
        hosts=[],
        concurrency=1,
        )
    parser.add_option("-f", "--devices-file", dest="devices_file", help="list/url of devices.json")
    parser.add_option("-H", "--host", dest="hosts", action="append")
    parser.add_option("-j", dest="concurrency", type="int")

    options, actions = parser.parse_args()

    if options.concurrency > 1:
        import multiprocessing

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
        if options.concurrency == 1:
            for foopy in selected_foopies:
                run_action_on_foopy(action, foopy)
        else:
            p = multiprocessing.Pool(processes=options.concurrency)
            results = []
            for foopy in selected_foopies:
                result = p.apply_async(run_action_on_foopy, (action, foopy) )
                results.append( (foopy, result) )
            p.close()
            failed = False
            for foopy, result in results:
                if not result.get():
                    print foopy, "FAILED"
                    failed = True
            p.join()
            if failed:
                sys.exit(1)

