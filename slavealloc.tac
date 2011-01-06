from twisted.application import service
from slavealloc.application import Allocator

application = service.Application("slavealloc")
allocator = Allocator(http_port='tcp:8010', db_url='sqlite:////tmp/test.db')
allocator.setServiceParent(application)
