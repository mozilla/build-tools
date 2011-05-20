#!/usr/bin/python
import master_fabric
from fabric.api import env
from fabric.context_managers import settings
from Crypto.Random import atfork

def run_action_on_master(action, master):
    atfork()
    try:
        action_func = getattr(master_fabric, action)
        with settings(host_string=master['hostname']):
            action_func(master)
            return True
    except:
        import traceback
        print "Failed to run", action, "on", master['name']
        print traceback.format_exc()
        return False

if __name__ == '__main__':
    import sys
    import urllib
    from optparse import OptionParser
    import textwrap
    try:
        import simplejson as json
    except ImportError:
        import json

    parser = OptionParser("""%%prog [options] action [action ...]

Supported actions:
%s""" % textwrap.fill(", ".join(master_fabric.actions)))

    parser.set_defaults(
            hosts=[],
            roles=[],
            concurrency=1,
            show_list=False,
            all_masters=False,
            )
    parser.add_option("-f", "--master-file", dest="master_file", help="list/url of masters")
    parser.add_option("-H", "--host", dest="hosts", action="append")
    parser.add_option("-R", "--role", dest="roles", action="append")
    parser.add_option("-j", dest="concurrency", type="int")
    parser.add_option("-l", dest="show_list", action="store_true", help="list hosts")
    parser.add_option("--all", dest="all_masters", action="store_true", help="work on all masters, not just enabled ones")

    options, actions = parser.parse_args()

    if options.concurrency > 1:
        import multiprocessing

    if not options.master_file:
        parser.error("master-file is required")

    if not actions and not options.show_list:
        parser.error("at least one action is required")

    # Load master data
    all_masters = json.load(urllib.urlopen(options.master_file))

    masters = []

    for m in all_masters:
        if not m['enabled'] and not options.all_masters:
            continue
        if m['name'] in options.hosts:
            masters.append(m)
        elif m['role'] in options.roles:
            masters.append(m)
        elif 'all' in options.hosts or 'all' in options.roles:
            masters.append(m)

    if options.show_list:
        if len(masters) == 0:
            masters = [m for m in all_masters if m['enabled'] or options.all_masters]

        fmt = "%(role)-9s %(name)-14s %(hostname)s:%(basedir)s"
        print fmt % dict(role='role', name='name', hostname='hostname',
                basedir='basedir')
        for m in masters:
            print fmt % m
        sys.exit(0)

    if len(masters) == 0:
        parser.error("You need to specify a master via -H and/or -R")

    env.user = 'cltbld'
    for action in actions:
        if options.concurrency == 1:
            for master in masters:
                run_action_on_master(action, master)
        else:
            p = multiprocessing.Pool(processes=options.concurrency)
            results = []
            for master in masters:
                result = p.apply_async(run_action_on_master, (action, master) )
                results.append( (master, result) )
            p.close()
            failed = False
            for master, result in results:
                if not result.get():
                    print master['name'], "FAILED"
                    failed = True
            p.join()
            if failed:
                sys.exit(1)
