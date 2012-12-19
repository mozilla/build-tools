from fabric.api import run
from fabric.context_managers import cd, hide, show
from fabric.context_managers import settings
from fabric.colors import green, yellow, red

OK = green('[OK]  ')
FAIL = red('[FAIL]')
INFO = yellow('[INFO]')

def per_host(fn):
    fn.per_host = True
    return fn

def per_device(fn):
    fn.per_device = True
    return fn

@per_host
def show_revision(foopy):
    with hide('stdout', 'stderr', 'running'):
        tools_rev = run('hg -R /builds/tools ident -i')

        print "%-14s %12s" % (foopy, tools_rev)

@per_host
def update(foopy):
    with show('running'):
        with cd('/builds/tools'):
            run('hg pull && hg update -C')
            with hide('stdout', 'stderr', 'running'):
                tools_rev = run('hg ident -i')
    
    print OK, "updated %s tools to %12s" % (foopy, tools_rev)

@per_device
def stop_cp(device):
    with show('running'):
        with cd('/builds'):
            run('./stop_cp.sh %s' % device)
        print OK, "Stopped clientproxy for %s" % (device)

@per_device
def what_master(device):
    import re
    with hide('stdout', 'stderr', 'running'):
        with cd('/builds'):
            tac_path = './%s/buildbot.tac' % device
            tac_exists = False
            with settings(hide('everything'), warn_only=True):
                tac_exists = not run('test -e "$(echo %s)"' % tac_path).failed
            if tac_exists:
                output = run('cat %s | grep "^buildmaster_host"' % tac_path)
                m = re.search('^buildmaster_host\s*=\s*([\'"])(.*)[\'"]', output, re.M)
                if not m:
                    print FAIL, "Failed to parse buildbot.tac:", repr(output)
                    master = "No Master"
                else:
                    master = m.group(2)
            else:
                master = "No Master"
        print OK, "%s uses %s" % (device, master)

actions = [
    'what_master',
    'show_revision',
    'update',
    'stop_cp',
    ]
