import sys
from slavealloc import exceptions
from slavealloc.logic import allocate, buildbottac

def setup_argparse(subparsers):
    subparser = subparsers.add_parser('gettac', help='get a tac file for a slave')
    subparser.add_argument('slave', nargs='*',
            help="slave hostnames to allocate for (no domain)")
    subparser.add_argument('-n', '--noop', dest='noop',
            default=False, action='store_true',
            help="don't actually allocate")
    subparser.add_argument('-q', '--quiet', dest='quiet',
            default=False, action='store_true',
            help="don't actually output the tac file; just the allocation made")
    return subparser

def process_args(subparser, args):
    if not args.slave:
        subparser.error("at least one slave name is required")
    if '.' in ''.join(args.slave):
        subparser.error("slave name must not contain '.'; give the unqualified hostname")

def main(args):
    for slave in args.slave:
        try:
            allocation = allocate.Allocation(slave)
        except exceptions.NoAllocationError:
            print >>sys.stderr, "No buildbot.tac available (404 from slave allocator)"
            sys.exit(1)

        if not args.quiet:
            print buildbottac.make_buildbot_tac(allocation)

        if not args.noop:
            allocation.commit()
        if allocation.enabled:
            print >>sys.stderr, "Allocated '%s' to '%s' (%s:%s)" % (slave,
                allocation.master_nickname,
                allocation.master_fqdn,
                allocation.master_pb_port)
        else:
            print >>sys.stderr, "Slave '%s' is disabled; no allocation made" % slave
