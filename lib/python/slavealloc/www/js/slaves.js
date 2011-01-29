$(document).ready(function () {

// MODELS

var Slave = Backbone.Model.extend();

var Slaves = Backbone.Collection.extend({
    url: '/api/slaves',
    model: Slave,

    // information about expected columns
    columns: [
        { id: "name", sTitle: "Name", },
        { id: "datacenter", sTitle: "Datacenter", },
        { id: "trustlevel", sTitle: "Trust", },
        { id: "bitlength", sTitle: "Bits", },
        { id: "environment", sTitle: "Environ", },
        { id: "purpose", sTitle: "Purpose", },
        { id: "pool", sTitle: "Pool", },
        { id: "distro", sTitle: "Distro", },
    ],

});

// VIEWS

var SlavesView = Backbone.View.extend({
    tagName: 'div',
    className: 'demo-jui',

    initialize : function (args) {
        _.bindAll(this, 'addSlave', 'refresh', 'render');

        this.model.bind('refresh', this.refresh);
        this.model.bind('add', this.addSlave);
        this.model.bind('remove', this.addSlave);
    },

    render: function() {
        // dataTable likes to add sibling nodes, so add the table within
        // the enclosing div, this.el
        $(this.el).append('<table class="display" ' +
            'cellspacing="0" cellpadding="0" border="0"></table>');

        // note that the dataTable isn't added until we've got the data
        return this;
    },

    addSlave : function (slave) {
        var slave_view = new SlaveView({model: slave});
        this.$('tbody').append(slave_view.render().el);
    },

    refresh : function (args) {
        var dt = this.dt;
        var model = this.model;

        // NOTE: this assumes refresh is only called once
        var aaData = model.map(function(slave_model) {
            var row = _.map(model.columns, function(col) {
                return slave_model.get(col.id);
            });
            return row;
        });

        var aoColumns = model.columns.map(function(col) {
            var rv = { sTitle: col.sTitle };
            return rv;
        });

        $('table').dataTable({
            aaData: aaData,
            aoColumns: aoColumns,
            bJQueryUI: true,
            bPaginate: false,
            bAutoWidth: false,
        });
    },
});

// SETUP

// set up model
var slaves = new Slaves();
slaves.fetch();

// set up view
var slaves_view = new SlavesView({model: slaves});
$('body').append(slaves_view.render().el);

});
