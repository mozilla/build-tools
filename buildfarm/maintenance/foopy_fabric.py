from fabric.api import run
from fabric.context_managers import cd, hide, show
from fabric.colors import green

OK = green('[OK]')

def show_revision(foopy):
    with hide('stdout', 'stderr', 'running'):
        tools_rev = run('hg -R /builds/tools ident -i')

        print "%-14s %12s" % (foopy, tools_rev)

def update(foopy):
    with show('running'):
        with cd('/builds/tools'):
            run('hg pull && hg update -C')
            with hide('stdout', 'stderr', 'running'):
                tools_rev = run('hg ident -i')
    
    print OK, "updated %s tools to %12s" % (foopy, tools_rev)


actions = [
    'show_revision',
    'update',
    ]
