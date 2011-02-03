import sqlalchemy as sa
import simplejson
from twisted.internet import defer
from twisted.python import log
from twisted.web import resource, server, error
from slavealloc import exceptions
from slavealloc.data import queries, model

# base classes

class Collection(resource.Resource):
    addSlash = True
    isLeaf = False
    def getChild(self, name, request):
        if name:
            return self.instance_class(name)

    def render_GET(self, request):
        res = self.query.execute()
        request.setHeader('content-type', 'application/json')
        return simplejson.dumps([ dict(r.items()) for r in res.fetchall() ])

class Instance(resource.Resource):
    isLeaf = True
    ok_response = simplejson.dumps(dict(success=True))

    def __init__(self, id):
        self.id = id

    def render_PUT(self, request):
        json = simplejson.load(request.content)
        args = dict((k, json[k]) for k in self.update_keys)
        log.msg("%s: updating id %s from %r" %
                (self.__class__.__name__, self.id, args))
        args['id'] = self.id
        self.update_query.execute(args)
        return self.ok_response

# concrete classes

class SlaveResource(Instance):
    update_query = model.masters.update(
            model.masters.c.masterid == sa.bindparam('id'))
    update_keys = ('poolid',)

class SlavesResource(Collection):
    instance_class = SlaveResource
    query = queries.denormalized_slaves

class MasterResource(Instance):
    update_query = model.masters.update(
            model.masters.c.masterid == sa.bindparam('id'))
    update_keys = ('poolid',)

class MastersResource(Collection):
    instance_class = MasterResource
    query = queries.denormalized_masters

class PoolResource(Instance):
    def render_GET(self, request):
        return 'i m a master'

class PoolsResource(Collection):
    instance_class = PoolResource
    query = model.pools.select()

class ApiRoot(resource.Resource):
    addSlash = True
    isLeaf = False

    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild('slaves', SlavesResource())
        self.putChild('masters', MastersResource())
        self.putChild('pools', PoolsResource())

def makeRootResource():
    return ApiRoot()
