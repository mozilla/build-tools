import argparse

from slavealloc.data import engine, model

# subcommands
from slavealloc.scripts import dbinit, gettac, lock, disable, dbdump
subcommands = [ dbinit, gettac, lock, disable, dbdump ]

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

    # set up the SQLAlchemy binding of metadata to engine
    eng = engine.create_engine(args)
    model.metadata.bind = eng

    args.module.process_args(args.subparser, args)

    return args.module.main, args

def main():
    func, args = parse_options()
    func(args)
