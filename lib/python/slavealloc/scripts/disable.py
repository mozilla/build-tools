import sys
from slavealloc import exceptions
from slavealloc.data import model

def setup_argparse(subparsers):
    subparser = subparsers.add_parser('disable', help='disable a slave, preventing it from starting')
    subparser.add_argument('slave',
            help="slave to disable (or enable with --enable)")
    subparser.add_argument('-e', '--enable', dest='enable',
            default=False, action='store_true',
            help="enable a disabled slave")
    return subparser

def process_args(subparser, args):
    if not args.slave:
        subparser.error("slave name is required")
    if '.' in ''.join(args.slave):
        subparser.error("slave name must not contain '.'; give the unqualified hostname")

def main(args):
    q = model.slaves.update(values=dict(enabled=args.enable),
            whereclause=(model.slaves.c.name == args.slave))
    if not q.execute().rowcount:
        print >>sys.stderr, "No slave found named '%s'." % args.slave
        sys.exit(1)
    else:
        print >>sys.stderr, "%s '%s'" % (
                {True : 'Enabled', False : 'Disabled'}[args.enable],
                args.slave)
