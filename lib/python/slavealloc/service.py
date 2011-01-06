from twisted.python import log
from twisted.internet import defer
from twisted.application import service, strports

class AllocatorService(service.Service):
    
    def __init__(self, db_url):
        self.db_url = db_url

    def startService(self):
        log.msg("starting AllocatorService with db_url='%s'" % self.db_url)
        service.Service.startService(self)

    def stopService(self):
        log.msg("stopping AllocatorService")
        return service.Service.stopService(self)

    def getBuildbotTac(self, slave_name):
        return defer.succeed("fake buildbot.tac")
