import sys
import csv
import collections
import sqlalchemy as sa
from slavealloc.data import model, queries

silo_keys = 'environment purpose distro bitlength datacenter trustlevel'.split()

def setup_argparse(subparsers):
    subparser = subparsers.add_parser('silos', help='show slave silos with counts')
    subparser.add_argument('-c', '--columns', dest='columns',
            help='comma-separated list of columns to show',
            default=','.join(silo_keys))
    subparser.add_argument('-s', '--sort', dest='sort',
            help='comma-separated list of columns to sort on; defaluts to COLUMNS. ' +
                 'note that \'count\' is a valid sort key, too',
            default=None)
    subparser.add_argument('--csv', dest='csv', default=False, action='store_true',
            help='output in CSV format')
    return subparser

def process_args(subparser, args):
    args.columns = [ c.strip() for c in args.columns.split(',') ]

    unrecognized_columns = set(args.columns) - set(silo_keys)
    if unrecognized_columns:
        subparser.error("unrecognized columns: %s" % (" ".join(list(unrecognized_columns)),))

    if args.sort is None:
        args.sort = args.columns[:]
    else:
        args.sort = [ c.strip() for c in args.sort.split(',') ]

    unrecognized_keys = set(args.sort) - set(args.columns) - set(['count'])
    if unrecognized_keys:
        subparser.error("sort keys not available: %s" % (" ".join(list(unrecognized_keys)),))

def main(args):
    silos = collections.defaultdict(lambda : 0)

    # get the denormalized slave data
    q = queries.denormalized_slaves
    slaves = [ r for r in q.execute() ]

    # count the slaves into silos, using a key composed of the desired
    # columns.
    for slave in slaves:
        k = tuple(slave[c] for c in args.columns)
        silos[k] += 1

    # add the count to the end of 'columns' and 'silos'
    col_titles = args.columns + ['count']
    rows = [ k + (count,) for k, count in silos.iteritems() ]

    # sort the rows
    sortidxes = [ col_titles.index(col) for col in args.sort ]
    def keyfunc(row):
        return [ row[i] for i in sortidxes ]
    rows.sort(key=keyfunc)

    # shorten up some long names
    for long, short in [ ('datacenter', 'dc'), ('bitlength', 'bits') ]:
        if long in col_titles:
            col_titles[args.columns.index(long)] = short

    if args.csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(col_titles)
        for row in rows:
            writer.writerow(row)
    else:
        # calculate an appropriate format for the observed lengths
        lengths = [ max([ len(col_titles[i]) ] + [ len(str(row[i])) for row in rows ])
                    for i in xrange(len(col_titles)) ]
        fmtmsg = " ".join(["%%-%ds" % l for l in lengths])

        print fmtmsg % tuple(col_titles)
        for row in rows:
            print fmtmsg % row
