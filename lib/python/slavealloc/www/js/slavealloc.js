var js_root = '/ui/js/';
load(
    js_root + 'deps/jquery-1.4.4.min.js',
    js_root + 'deps/underscore-min.js')
.thenLoad(
    js_root + 'deps/jquery.dataTables.min.js',
    js_root + 'deps/jquery-ui-1.8.9.custom.min.js',
    js_root + 'deps/backbone.js') // TODO: switch back to -min
.thenLoad(
    js_root + 'models.js',
    js_root + 'views.js',
    js_root + 'controller.js')
.thenRun(
    function (next) {
        window.masters = new Masters();
        window.masters.fetch({ success: next });
    },
    function (next) {
        window.slaves = new Slaves();
        window.slaves.fetch({ success: next });
    },
    function (next) {
        window.distros = new Distros();
        window.distros.fetch({ success: next });
    },
    function (next) {
        window.datacenters = new Datacenters();
        window.datacenters.fetch({ success: next });
    },
    function (next) {
        window.bitlengths = new Bitlengths();
        window.bitlengths.fetch({ success: next });
    },
    function (next) {
        window.purposes = new Purposes();
        window.purposes.fetch({ success: next });
    },
    function (next) {
        window.trustlevels = new Trustlevels();
        window.trustlevels.fetch({ success: next });
    },
    function (next) {
        window.environments = new Environments();
        window.environments.fetch({ success: next });
    },
    function (next) {
        window.pools = new Pools();
        window.pools.fetch({ success: next });
    })
.thenRun(function () {
    // fire up the controller and start the history mgmt
    var controller = new SlaveallocController();
    Backbone.history.start();
});
