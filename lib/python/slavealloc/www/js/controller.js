SlaveallocController = Backbone.Controller.extend({
    initialize: function(args) {
        this.activateRoute = $.proxy(this, 'activateRoute');

        viewSpecs = [
            { name: '', view: new DashboardView(), title: null,
              rendered: false },
            { name: 'slaves', view: new SlavesTableView(),
              title: 'Slaves', rendered: false },
            { name: 'masters', view: new MastersTableView(),
              title: 'Masters', rendered: false },
            { name: 'silos', view: new SilosTableView(),
              title: 'Silos', rendered: false }
        ];

        this.currentViewSpec = null;

        this.viewTabsView = new ViewTabsView({
            viewSpecs: viewSpecs,
            el: $('#viewtabs')
        });
        this.viewTabsView.render();

        var self = this;
        $.each(viewSpecs, function (i, viewSpec) {
            self.route(viewSpec.name, viewSpec.name,
                       function() { self.activateRoute(viewSpec); });
        });
    },

    activateRoute: function(viewSpec) {
        // done loading..
        $('.loading').remove();

        // render the new one, if necessary
        // TODO: spinner
        if (!viewSpec.rendered) {
            viewSpec.view.render();
            $(viewSpec.view.el).hide();
            $('#viewcontent').append(viewSpec.view.el);
            viewSpec.rendered = true;
        }

        // hide the previous view from the DOM
        if (this.currentViewSpec) {
            $(this.currentViewSpec.view.el).hide();
        }

        // .. and show the new one
        $(viewSpec.view.el).show();

        // then record the updated current view
        this.currentViewSpec = viewSpec;
    }
});
