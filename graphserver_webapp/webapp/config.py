class Config(object):
    DEBUG = False
    TESTING = False
    DATABASE_URI = 'sqlite:///:memory:'
    VERSION = 'Default'

class TestConfig(object):
    DEBUG = True
    TESTING = True
    DATABASE_URI = 'sqlite:///test_graphserver.sqlite'
    VERSION = 'Test'
    LOGFILE = 'test.log'

class ProductionConfig(Config):
    DATABASE_URI = 'mysql://user@localhost/foo'
    VERSION = 'Production'
    SECRET_KEY = 'FILLMEIN'
    LOGFILE = 'graphserver_webapp.log'

class DevelopmentConfig(Config):
    DATABASE_URI = 'mysql://root:password@localhost/graphserver_staging'
    DEBUG = True
    SECRET_KEY = 'developmentkey'
    VERSION = 'Staging'
    LOGFILE = 'staging.log'
