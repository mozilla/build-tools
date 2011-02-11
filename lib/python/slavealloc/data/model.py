"""

Data storage for the slave allocator

"""

import sqlalchemy as sa

metadata = sa.MetaData()

# basic definitions

distros = sa.Table('distros', metadata,
    sa.Column('distroid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text, nullable=False),
)

datacenters = sa.Table('datacenters', metadata,
    sa.Column('dcid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text, nullable=False),
)

bitlengths = sa.Table('bitlengths', metadata,
    sa.Column('bitsid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text, nullable=False),
)

purposes = sa.Table('purposes', metadata,
    sa.Column('purposeid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text, nullable=False),
)

trustlevels = sa.Table('trustlevels', metadata,
    sa.Column('trustid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text, nullable=False),
)

environments = sa.Table('environments', metadata,
    sa.Column('envid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text, nullable=False),
)

# pools

pools = sa.Table('pools', metadata,
    sa.Column('poolid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text, nullable=False),
)

# slave passwords, based on pool and distro

slave_passwords = sa.Table('slave_passwords', metadata,
    # for most pools, all slaves have the same password, but for some pools,
    # different distros have different passwords.  Needless complexity FTW!
    # If the distro column is NULL, that is considered a wildcard and will match
    # all distros.
    sa.Column('poolid', sa.Integer, sa.ForeignKey('pools.poolid'), nullable=False),
    sa.Column('distroid', sa.Integer, sa.ForeignKey('distros.distroid')),
    sa.Column('password', sa.Text, nullable=False),
)

# all slaves

slaves = sa.Table('slaves', metadata,
    sa.Column('slaveid', sa.Integer, primary_key=True),
    sa.Column('name', sa.Text, nullable=False),

    # silo
    sa.Column('distroid', sa.Integer, sa.ForeignKey('distros.distroid'), nullable=False),
    sa.Column('bitsid', sa.Integer, sa.ForeignKey('bitlengths.bitsid'), nullable=False),
    sa.Column('purposeid', sa.Integer, sa.ForeignKey('purposes.purposeid'), nullable=False),
    sa.Column('dcid', sa.Integer, sa.ForeignKey('datacenters.dcid'), nullable=False),
    sa.Column('trustid', sa.Integer, sa.ForeignKey('trustlevels.trustid'), nullable=False),
    sa.Column('envid', sa.Integer, sa.ForeignKey('environments.envid'), nullable=False),
    sa.Column('poolid', sa.Integer, sa.ForeignKey('pools.poolid'), nullable=False),

    # config
    sa.Column('basedir', sa.Text, nullable=False),
    sa.Column('locked_masterid', sa.Integer, sa.ForeignKey('masters.masterid')),
    sa.Column('enabled', sa.Boolean, nullable=False, default=True),

    # state
    sa.Column('current_masterid', sa.Integer, sa.ForeignKey('masters.masterid')),
)

# masters

masters = sa.Table('masters', metadata,
    sa.Column('masterid', sa.Integer, primary_key=True),
    sa.Column('nickname', sa.Text, nullable=False),
    sa.Column('fqdn', sa.Text, nullable=False),
    sa.Column('http_port', sa.Integer, nullable=False),
    sa.Column('pb_port', sa.Integer, nullable=False),
    sa.Column('dcid', sa.Integer, sa.ForeignKey('datacenters.dcid'), nullable=False),
    sa.Column('poolid', sa.Integer, sa.ForeignKey('pools.poolid'), nullable=False),
)
