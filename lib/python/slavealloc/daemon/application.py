from twisted.application import service as tw_service, strports
from slavealloc.daemon import service as service, http

class Allocator(tw_service.MultiService):
    def __init__(self, http_port, db_url):
        tw_service.MultiService.__init__(self)

        self.allocator = service.AllocatorService(db_url)
        self.allocator.setServiceParent(self)

        self.site = http.AllocatorSite(self.allocator)
        self.httpservice = strports.service(http_port, self.site)
        self.httpservice.setServiceParent(self)
