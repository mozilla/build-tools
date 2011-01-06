"""

Data storage for the slave allocator

"""

import sqlalchemy as sa

metadata = sa.MetaData()

# basic definitions

distros = sa.Table('distros', metadata,
    sa.Column('distroid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text),
)

datacenters = sa.Table('datacenters', metadata,
    sa.Column('dcid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text),
)

bitlengths = sa.Table('bitlengths', metadata,
    sa.Column('bitsid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text),
)

purposes = sa.Table('purposes', metadata,
    sa.Column('purposeid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text),
)

trustlevels = sa.Table('trustlevels', metadata,
    sa.Column('trustid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text),
    sa.Column('order', sa.Integer), # higher is more restricted
)

environments = sa.Table('environments', metadata,
    sa.Column('envid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text),
)

# pools

pools = sa.Table('pools', metadata,
    sa.Column('poolid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text),
)

# all slaves

slaves = sa.Table('slaves', metadata,
    sa.Column('slaveid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text),
    sa.Column('distroid', sa.Integer, sa.ForeignKey('distros.distroid')),
    sa.Column('bitsid', sa.Integer, sa.ForeignKey('bitlengths.bitsid')),
    sa.Column('purposeid', sa.Integer, sa.ForeignKey('purposes.purposeid')),
    sa.Column('dcid', sa.Integer, sa.ForeignKey('datacenters.dcid')),
    sa.Column('trustid', sa.Integer, sa.ForeignKey('trustlevels.trustid')),
    sa.Column('envid', sa.Integer, sa.ForeignKey('environments.envid')),
    sa.Column('poolid', sa.Integer, sa.ForeignKey('pools.poolid')),
    sa.Column('current_masterid', sa.Integer, sa.ForeignKey('masters.masterid')),
)

# masters

masters = sa.Table('masters', metadata,
    sa.Column('masterid', sa.Integer, primary_key=True),
    sa.Column('nickname', sa.Text),
    sa.Column('fqdn', sa.Text),
    sa.Column('http_port', sa.Integer),
    sa.Column('pb_port', sa.Integer),
    sa.Column('dcid', sa.Integer, sa.ForeignKey('datacenters.dcid')),
    sa.Column('poolid', sa.Integer, sa.ForeignKey('pools.poolid')),
)

# TODO: think about what kinds of indices are best: aggregate? individual?
