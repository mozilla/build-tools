from twisted.application import service
from slavealloc.daemon.application import Allocator
from twisted.python.logfile import LogFile
from twisted.python.log import ILogObserver, FileLogObserver

application = service.Application("slavealloc")

# set up logfile rotation
logfile = LogFile.fromFullPath("slavealloc.log", rotateLength=1024**2,
			 maxRotatedFiles=10)
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)

allocator = Allocator(http_port='tcp:8010', db_url='sqlite:///slavealloc.db',
    run_ui=True)
allocator.setServiceParent(application)
