from twisted.application import service
from slavealloc.daemon.application import Allocator

application = service.Application("slavealloc")
allocator = Allocator(http_port='tcp:8010', db_url='sqlite:///slavealloc.db',
    run_allocator=True)
allocator.setServiceParent(application)
