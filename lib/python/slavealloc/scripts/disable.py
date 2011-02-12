import sys
from twisted.internet import defer, reactor
from slavealloc import client, exceptions

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

def bool_to_word(bool):
    return {True : 'enabled', False : 'disabled'}[bool]

@defer.inlineCallbacks
def main(args):
    agent = client.RestAgent(reactor, args.apiurl)

    # first get the slaveid
    path = 'slaves/%s?byname=1' % args.slave
    slave = yield agent.restRequest('GET', path, {})
    if not slave:
        raise exceptions.CmdlineError(
                "No slave found named '%s'." % args.slave)
    assert slave['name'] == args.slave
    slaveid = slave['slaveid']

    # then set its state, if not already set
    if ((args.enable and not slave['enabled']) or 
        (not args.enable and slave['enabled'])):
        set_result = yield agent.restRequest('PUT',
                    'slaves/%d' % slaveid,
                    { 'enabled' : args.enable })
        success = set_result.get('success')
        if not success:
            raise exceptions.CmdlineError("Operation failed on server.")
        print >>sys.stderr, "%s %s" % (
                args.slave, bool_to_word(args.enable))
    else:
        print >>sys.stderr, "%s is already %s" % (
                args.slave, bool_to_word(args.enable))
