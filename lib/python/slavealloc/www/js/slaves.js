$(document).ready(function () {

// MODELS

var Slave = Backbone.Model.extend();

var Slaves = Backbone.Collection.extend({
    url: '/api/slaves',
    model: Slave,

    // information about expected columns
    columns: [
        { id: "name", title: "Name", cls: 'slave-name', },
        { id: "datacenter", title: "Datacenter", cls: 'slave-datacenter', },
        { id: "trustlevel", title: "Trust", cls: 'slave-trustlevel', },
        { id: "bitlength", title: "Bits", cls: 'slave-bitlength', },
        { id: "environment", title: "Environ", cls: 'slave-environment', },
        { id: "purpose", title: "Purpose", cls: 'slave-purpose', },
        { id: "pool", title: "Pool", cls: 'slave-pool', },
        { id: "distro", title: "Distro", cls: 'slave-distro', },
    ],

});

// VIEWS

var SlaveView = Backbone.View.extend({
    // specifiy the element information
    tagName: 'tr',
    className: 'slave-row',

    initialize: function () {
        _.bindAll(this, 'changeDatacenter', 'handleDatacenterClick', 'render', 'rerender');

        this.model.bind('change', this.rerender);
    },

    events: {
        'click .slave-datacenter': 'handleDatacenterClick',
    },

    render: function () {
        var el = $(this.el);
        var model = this.model;

        // generate the elements dynamically from the columns
        _.each(model.collection.columns, function(col) {
            el.append('<td class="' + col.cls + '">' + model.get(col.id) + '</td>');
        });

        return this;
    },

    rerender: function() {
        var model = this.model;
        var el = $(this.el);

        // update all of the existing elements' values
        _.each(this.model.collection.columns, function(col) {
            el.find('td.' + col.cls).text(model.get(col.id));
        });
    },

    handleDatacenterClick: function() {
        this.model.set({ datacenter: this.model.get('datacenter') + ' more',
                         bitlength: 128, });
    },
});

var SlavesView = Backbone.View.extend({
    tagName: 'div',
    className: 'slave-view',

    initialize : function (args) {
        _.bindAll(this, 'addSlave', 'addAll', 'render');

        this.model.bind('refresh', this.addAll);
        this.model.bind('add', this.addSlave);
        this.model.bind('remove', this.addSlave);
    },

    render: function() {
        $(this.el).append('<table><thead><tr></tr></thead><tbody></tbody></table>');

        var tr = this.$('thead tr');
        _.each(this.model.columns, function(col) {
            tr.append('<th>' + col.title + '</th>');
        });

        return this;
    },

    addSlave : function (slave) {
        var slave_view = new SlaveView({model: slave});
        this.$('tbody').append(slave_view.render().el);
    },

    addAll : function (args) {
        // NOTE: this assumes refresh is only called once
        this.model.each(this.addSlave);
    },
});

// CONTROLLER (er, sorta)

var slaves = new Slaves();
var slaves_view = new SlavesView({model: slaves});
$('body').append(slaves_view.render().el);
slaves.fetch();
});
