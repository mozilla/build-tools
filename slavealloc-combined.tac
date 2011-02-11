from twisted.application import service
from slavealloc.daemon.application import Allocator

application = service.Application("slavealloc")
allocator = Allocator(http_port='tcp:8012', db_url='sqlite:///slavealloc.db',
    run_allocator=True,
    run_ui=True)
allocator.setServiceParent(application)
