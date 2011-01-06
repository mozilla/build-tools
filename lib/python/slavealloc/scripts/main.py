import sys
import argparse
import textwrap

from slavealloc.data import engine

# subcommands
from slavealloc.scripts import silos, dbinit, pools, gettac
subcommands = [ silos, dbinit, pools, gettac ]

def parse_options():
    parser = argparse.ArgumentParser(description="Runs slavealloc subcommands")
    parser.set_defaults(_module=None)

    engine.add_data_arguments(parser)

    subparsers = parser.add_subparsers(title='subcommands')

    for module in subcommands:
        subparser = module.setup_argparse(subparsers)
        subparser.set_defaults(module=module, subparser=subparser)

    args = parser.parse_args()

    if not args.module:
        parser.error("No subcommand specified")

    args.module.process_args(args.subparser, args)

    return args.module.main, args

def main():
    func, args = parse_options()
    try:
        func(args)
    except engine.NoDBError:
        print >>sys.stderr, "No database specified (use --db)"
        sys.exit(1)

