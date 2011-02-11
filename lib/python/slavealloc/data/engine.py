import sqlalchemy as sa

class NoDBError(Exception):
    pass

def add_data_arguments(parser):
    parser.add_argument('-D', '--db', dest='dburl',
            default='sqlite:///slavealloc.db', # temporary
            help='SQLAlchemy database URL')

def create_engine(args):
    if not args.dburl:
        raise NoDBError
    return sa.create_engine(args.dburl)
