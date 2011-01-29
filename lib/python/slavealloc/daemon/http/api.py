import simplejson
from twisted.internet import defer
from twisted.python import log
from twisted.web import resource, server, error
from slavealloc import exceptions
from slavealloc.data import queries, model

class SlaveResource(resource.Resource):
    isLeaf = True

    def __init__(self, name):
        self.name = name

    def render_GET(self, request):
        return 'i m a slave'

class SlavesResource(resource.Resource):
    addSlash = True
    isLeaf = False

    def getChild(self, name, request):
        if name:
            return SlaveResource(name)

    def render_GET(self, request):
        q = queries.denormalized_slaves.execute()
        #request.setHeader('content-type', 'application/json')
        return simplejson.dumps([ dict(r.items()) for r in q.fetchall() ])

class ApiRoot(resource.Resource):
    addSlash = True
    isLeaf = False

    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild('slaves', SlavesResource())

def makeRootResource():
    return ApiRoot()
