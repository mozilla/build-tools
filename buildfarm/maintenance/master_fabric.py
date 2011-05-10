from fabric.api import run
from fabric.context_managers import cd, hide, show
from fabric.operations import put

def check(master):
    """Checks that the master parameters are valid"""
    with hide('stdout', 'stderr', 'running'):
        date = run('date')
        run('test -d %(bbcustom_dir)s' % master)
        run('test -d %(bbconfigs_dir)s' % master)
        run('test -d %(master_dir)s' % master)
        run('test -d %(tools_dir)s' % master)

        assert run('hg -R %(bbcustom_dir)s ident -b' % master) == master['bbcustom_branch']
        assert run('hg -R %(bbconfigs_dir)s ident -b' % master) == master['bbconfigs_branch']
        assert run('hg -R %(tools_dir)s ident -b' % master) == master['tools_branch']
        print master['name'], date, "OK"

def checkconfig(master):
    """Runs buildbot checkconfig"""
    check(master)
    with hide('stdout', 'stderr'):
        with cd(master['basedir']):
            try:
                run('make checkconfig')
                print "%-14s OK" % master['name']
            except:
                print "%-14s FAILED" % master['name']
                raise

def show_revisions(master):
    """Reports the revisions of buildbotcustom, buildbot-configs"""
    with hide('stdout', 'stderr', 'running'):
        bbcustom_rev = run('hg -R %(bbcustom_dir)s ident -i' % master)
        bbconfigs_rev = run('hg -R %(bbconfigs_dir)s ident -i' % master)
        tools_rev = run('hg -R %(tools_dir)s ident -i' % master)

        bbcustom_rev = bbcustom_rev.split()[0]
        bbconfigs_rev = bbconfigs_rev.split()[0]
        tools_rev = tools_rev.split()[0]
        print "%-14s %12s %12s %12s" % (master['name'], bbcustom_rev,
                                        bbconfigs_rev, tools_rev)

def reconfig(master):
    print "starting reconfig of %(hostname)s:%(basedir)s" % master
    with show('running'):
        with cd(master['basedir']):
            put('buildbot-wrangler.py', '%s/buildbot-wrangler.py' % master['basedir'])
            run('rm -f *.pyc')
            run('python buildbot-wrangler.py reconfig %s' % master['master_dir'])
    print "finished reconfig of %(hostname)s:%(basedir)s" % master

def restart(master):
    with show('running'):
        with cd(master['basedir']):
            put('buildbot-wrangler.py', '%s/buildbot-wrangler.py' % master['basedir'])
            run('rm -f *.pyc')
            run('python buildbot-wrangler.py restart %s' % master['master_dir'])

def graceful_restart(master):
    with show('running'):
        with cd(master['basedir']):
            put('buildbot-wrangler.py', '%s/buildbot-wrangler.py' % master['basedir'])
            run('rm -f *.pyc')
            run('python buildbot-wrangler.py graceful_restart %s %s' % (master['master_dir'], master['http_port']))

def stop(master):
    with show('running'):
        with cd(master['basedir']):
            put('buildbot-wrangler.py', '%s/buildbot-wrangler.py' % master['basedir'])
            run('python buildbot-wrangler.py stop %s' % master['master_dir'])

def graceful_stop(master):
    with show('running'):
        with cd(master['basedir']):
            put('buildbot-wrangler.py', '%s/buildbot-wrangler.py' % master['basedir'])
            run('rm -f *.pyc')
            run('python buildbot-wrangler.py graceful_stop %s %s' % (master['master_dir'], master['http_port']))

def start(master):
    with show('running'):
        with cd(master['basedir']):
            put('buildbot-wrangler.py', '%s/buildbot-wrangler.py' % master['basedir'])
            run('rm -f *.pyc')
            run('python buildbot-wrangler.py start %s' % master['master_dir'])

def update(master):
    with show('running'):
        with cd(master['bbcustom_dir']):
            run('hg pull')
            run('hg update -r %s' % master['bbcustom_branch'])
        with cd(master['bbconfigs_dir']):
            run('hg pull')
            run('hg update -r %s' % master['bbconfigs_branch'])
        with cd(master['tools_dir']):
            run('hg pull')
            run('hg update -r %s' % master['tools_branch'])

actions = [
    'check',
    'checkconfig',
    'show_revisions',
    'reconfig',
    'restart',
    'graceful_restart',
    'stop',
    'graceful_stop',
    'start',
    'update',
    ]

