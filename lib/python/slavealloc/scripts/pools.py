import sys
import csv
import collections
import sqlalchemy as sa
from slavealloc.data import model, queries

pools_keys = 'pool nmasters nslaves masters'.split()

def setup_argparse(subparsers):
    subparser = subparsers.add_parser('pools', help='show master pools')
    subparser.add_argument('-c', '--columns', dest='columns',
            help='comma-separated list of columns to show',
            default=','.join(pools_keys))
    return subparser

def process_args(subparser, args):
    args.columns = [ c.strip() for c in args.columns.split(',') ]

    unrecognized_columns = set(args.columns) - set(pools_keys)
    if unrecognized_columns:
        subparser.error("unrecognized columns: %s" % (" ".join(list(unrecognized_columns)),))

def main(args):
    pools = collections.defaultdict(lambda:
            dict(masters=[], nmasters=0, nslaves=0))

    col_titles = args.columns

    if 'nmasters' in col_titles or 'masters' in col_titles:
        q = queries.denormalized_masters
        for master in q.execute():
            p = pools[master.pool]
            p['nmasters'] += 1
            p['masters'].append(master.nickname)

    if 'nslaves' in col_titles:
        q = queries.denormalized_slaves
        for slave in q.execute():
            p = pools[slave.pool]
            p['nslaves'] += 1

    datagrid = [col_titles]
    for name, pooldict in sorted(pools.items()):
        row = []
        for col in col_titles:
            if col == 'pool':
                row.append(name)
            elif col in ('nmasters', 'nslaves'):
                row.append(str(pooldict[col]))
            elif col == 'masters':
                row.append(' '.join(pooldict[col]))
        datagrid.append(row)

    fmtmsg = " ".join([
        "%%-%ds" % max(len(r[i]) for r in datagrid)
        for i in range(len(col_titles)) ])
    for row in datagrid:
        print fmtmsg % tuple(row)
