from twisted.python import log
from twisted.internet import defer
from twisted.application import service, strports
import sqlalchemy
from slavealloc.logic import allocate, buildbottac
from slavealloc import exceptions

class AllocatorService(service.Service):
    
    def __init__(self, db_url):
        self.db_url = db_url
        self.engine = sqlalchemy.create_engine(self.db_url)

    def startService(self):
        log.msg("starting AllocatorService with db_url='%s'" % self.db_url)
        service.Service.startService(self)
        # doesn't do anything for now..

    def stopService(self):
        log.msg("stopping AllocatorService")
        return service.Service.stopService(self)

    def getBuildbotTac(self, slave_name):
        # slave allocation is *synchronous* and happens in the main thread.
        # For now, this is a good thing - it allows us to ensure that multiple
        # slaves are not simultaneously reassigned.  This should be revisited
        # later.
        d = defer.succeed(None)
        def gettac(_):
            try:
                allocation = allocate.get_allocation(self.engine, slave_name)
            except exceptions.NoAllocationError:
                log.msg("rejecting slave '%s'" % slave_name)
                raise

            tac = buildbottac.make_buildbot_tac(self.engine, slave_name, allocation)

            allocate.allocate(self.engine, slave_name, allocation)
            log.msg("allocated '%s' to '%s' (%s:%s)" % (slave_name,
                    allocation.nickname, allocation.fqdn, allocation.pb_port))

            return tac
        d.addCallback(gettac)
        return d
