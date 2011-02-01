var js_root = '/ui/js/';
load(
    js_root + 'deps/jquery-1.4.4.min.js',
    js_root + 'deps/underscore-min.js')
.thenLoad(
    js_root + 'deps/jquery.dataTables.min.js',
    js_root + 'deps/jquery-ui-1.8.9.custom.min.js',
    js_root + 'deps/backbone-min.js')
.thenLoad(
    js_root + 'models.js',
    js_root + 'views.js')
.thenRun(function () { $(document).ready(run_page); });

run_page = function () {
    // set up models
    initializeModels();

    // set up view
    var slaves_view = new SlavesTableView();
    $('body').append(slaves_view.render().el);
};
