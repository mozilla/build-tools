import sys
from slavealloc import exceptions
from slavealloc.data import model

def setup_argparse(subparsers):
    subparser = subparsers.add_parser('lock', help='lock a slave to a particular master')
    subparser.add_argument('slave',
            help="slave to (un)lock")
    subparser.add_argument('master', nargs='?',
            help="master to lock it to")
    subparser.add_argument('-u', '--unlock', dest='unlock',
            default=False, action='store_true',
            help="unlock a locked slave (no need to specify master)")
    return subparser

def process_args(subparser, args):
    if not args.slave:
        subparser.error("slave name is required")
    if '.' in ''.join(args.slave):
        subparser.error("slave name must not contain '.'; give the unqualified hostname")
    if not args.master and not args.unlock:
        subparser.error("master name is required to lock")

def main(args):
    if args.unlock:
        q = model.slaves.update(values=dict(locked_masterid=None),
                whereclause=(model.slaves.c.name == args.slave))
        if not q.execute().rowcount:
            print >>sys.stderr, "No slave found named '%s'." % args.slave
            sys.exit(1)
        else:
            print >>sys.stderr, "Slave '%s' unlocked" % args.slave
    else:
        # find the masterid first
        q = model.masters.select(
                whereclause=(model.masters.c.nickname == args.master))
        r = q.execute()
        master_row = r.fetchone()
        if not master_row:
            print >>sys.stderr, "no master found with nickname '%s'." % args.master
            sys.exit(1)
        masterid = master_row.masterid

        q = model.slaves.update(values=dict(locked_masterid=masterid),
                whereclause=(model.slaves.c.name == args.slave))
        if not q.execute().rowcount:
            print >>sys.stderr, "No slave found named '%s'." % args.slave
            sys.exit(1)
        else:
            print >>sys.stderr, "Locked '%s' to '%s' (%s:%s)" % (args.slave,
                master_row.nickname, master_row.fqdn, master_row.pb_port)
