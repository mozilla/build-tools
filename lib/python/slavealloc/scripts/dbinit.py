import sys
import csv
from slavealloc.data import engine, model

def setup_argparse(subparsers):
    subparser = subparsers.add_parser('dbinit', help='initialize a fresh database')

    subparser.add_argument('--slave-data', dest='slave_data',
            help="""csv of slave data to import (columns: name, distro,
            bitlength, purpose, size, datacenter, trustlevel, and
            environment)""")

    subparser.add_argument('--master-data', dest='master_data',
            help="""csv of master data to import (columns: nickname, fqdn,
            http_port, pb_port, and pool)""")

    return subparser

def process_args(subparser, args):
    if not args.master_data or not args.slave_data:
        subparser.error("--master-data and --slave-data are both required")

def main(args):
    eng = engine.create_engine(args)
    model.metadata.bind = eng
    model.metadata.drop_all()
    model.metadata.create_all()

    rdr = csv.DictReader(open(args.slave_data))
    slaves = list(rdr)

    rdr = csv.DictReader(open(args.master_data))
    masters = list(rdr)

    def normalize(table, idcolumn, values):
        values = list(enumerate(list(set(values)))) # remove duplicates, add ids
        table.insert().execute([ { 'name' : n, idcolumn : i }
                                 for i, n in values ])
        return dict((n,i) for i, n in values)

    distros = normalize(model.distros, 'distroid',
            [ r['distro'] for r in slaves ])
    bitlengths = normalize(model.bitlengths, 'bitsid',
            [ r['bitlength'] for r in slaves ])
    purposes = normalize(model.purposes, 'purposeid',
            [ r['purpose'] for r in slaves ])
    datacenters = normalize(model.datacenters, 'dcid',
            [ r['datacenter'] for r in slaves ] +
            [ r['datacenter'] for r in masters ])
    trustlevels = normalize(model.trustlevels, 'trustid',
            [ r['trustlevel'] for r in slaves ])
    environments = normalize(model.environments, 'envid',
            [ r['environment'] for r in slaves ])
    pools = normalize(model.pools, 'poolid',
            [ r['pool'] for r in masters ])

    model.masters.insert().execute([
        dict(nickname=row['nickname'],
             fqdn=row['fqdn'],
             http_port=int(row['http_port']),
             pb_port=int(row['pb_port']),
             dcid=datacenters[row['datacenter']],
             poolid=pools[row['pool']])
        for row in masters ])

    model.slaves.insert().execute([
        dict(name=row['name'],
             distroid=distros[row['distro']],
             bitsid=bitlengths[row['bitlength']],
             purposeid=purposes[row['purpose']],
             dcid=datacenters[row['datacenter']],
             trustid=trustlevels[row['trustlevel']],
             envid=environments[row['environment']],
             poolid=pools[row['pool']],
             basedir=row['basedir'],
             current_masterid=None)
        for row in slaves ])
