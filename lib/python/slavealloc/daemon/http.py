from twisted.internet import defer
from twisted.python import log
from twisted.web import resource, server, error

class TacResource(resource.Resource):
    "dynamically created resource for a particular slave's buildbot.tac"
    isLeaf = True

    def __init__(self, slave_name):
        resource.Resource.__init__(self)
        self.slave_name = slave_name

    def render_GET(self, request):
        allocator = request.site.allocator
        d = defer.succeed(None)

        d.addCallback(lambda _ : allocator.getBuildbotTac(self.slave_name))

        def handle_success(buildbot_tac):
            request.setHeader('content-type', 'text/plain')
            request.write(buildbot_tac)
            request.finish()

        def handle_error(f):
            log.err(f, "while handling request for '%s'" % self.slave_name)
            request.setResponseCode(500)
            request.setHeader('content-type', 'text/plain')
            request.write('error processing request: %s' % f.getErrorMessage())
            request.finish()

        d.addCallbacks(handle_success, handle_error)

        # render_GET does not know how to wait for a Deferred, so we return
        # NOT_DONE_YET which has a similar effect
        return server.NOT_DONE_YET


class RootResource(resource.Resource):
    "root (/) resource for the HTTP service"
    addSlash = True
    isLeaf = False

    def getChild(self, name, request):
        return TacResource(name)


class AllocatorSite(server.Site):
    def __init__(self, allocator):
        server.Site.__init__(self, RootResource())
        self.allocator = allocator
