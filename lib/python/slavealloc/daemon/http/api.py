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
    update_query = model.slaves.update(
            model.slaves.c.slaveid == sa.bindparam('id'))
    # TODO: lock some of these down so they are not editable via the
    # interface
    update_keys = ('distroid', 'dcid', 'bitsid', 'purposeid', 'trustid',
                   'envid', 'poolid', 'basedir', 'locked_masterid', 'enabled')

class SlavesResource(Collection):
    instance_class = SlaveResource
    query = queries.denormalized_slaves

class MasterResource(Instance):
    update_query = model.masters.update(
            model.masters.c.masterid == sa.bindparam('id'))
    # TODO: lock some of these down so they are not editable via the
    # interface
    update_keys = ('nickname', 'fqdn', 'pb_port', 'http_port',
                   'poolid', 'dcid')

class MastersResource(Collection):
    instance_class = MasterResource
    query = queries.denormalized_masters

class DistroResource(Instance):
    pass

class DistrosResource(Collection):
    instance_class = DistroResource
    query = model.distros.select()

class DatacenterResource(Instance):
    pass

class DatacentersResource(Collection):
    instance_class = DatacenterResource
    query = model.datacenters.select()

class BitlengthResource(Instance):
    pass

class BitlengthsResource(Collection):
    instance_class = BitlengthResource
    query = model.bitlengths.select()

class PurposeResource(Instance):
    pass

class PurposesResource(Collection):
    instance_class = PurposeResource
    query = model.purposes.select()

class TrustlevelResource(Instance):
    pass

class TrustlevelsResource(Collection):
    instance_class = TrustlevelResource
    query = model.trustlevels.select()

class EnvironmentResource(Instance):
    pass

class EnvironmentsResource(Collection):
    instance_class = EnvironmentResource
    query = model.environments.select()

class PoolResource(Instance):
    pass

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
        self.putChild('distros', DistrosResource())
        self.putChild('datacenters', DatacentersResource())
        self.putChild('bitlengths', BitlengthsResource())
        self.putChild('purposes', PurposesResource())
        self.putChild('trustlevels', TrustlevelsResource())
        self.putChild('environments', EnvironmentsResource())
        self.putChild('pools', PoolsResource())

def makeRootResource():
    return ApiRoot()
