from twisted.application import service, strports
from slavealloc import service as sa_service, http

class Allocator(service.MultiService):
    def __init__(self, http_port, db_url):
        service.MultiService.__init__(self)

        self.allocator = sa_service.AllocatorService(db_url)
        self.allocator.setServiceParent(self)

        self.site = http.AllocatorSite(self.allocator)
        self.httpservice = strports.service(http_port, self.site)
        self.httpservice.setServiceParent(self)
