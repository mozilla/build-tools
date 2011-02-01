//
// Base Classes
//

var DenormalizedModel = Backbone.Model.extend({
    // call this to update denormalized columns (e.g., 'datacenter') to
    // their normalized column ('datacenterid') changes.
    bindDenormalizedColumns: function(column_info) {
        _.bindAll(this, '_bindDenormalizedColumn');
        _.each(column_info, this._bindDenormalizedColumn);
    },

    _bindDenormalizedColumn : function (info) {
        var change_fn = function (model, id) {
            var newname = info.model.get(id).get('name');
            var set = {};
            set[info.name_col] = newname;
            model.set(set);
        };

        this.bind('change:' + info.id_col, change_fn);
    },
});

//
// Slaves
//

var Slave = DenormalizedModel.extend({
    initialize: function() {
        this.id = this.get('name');

        this.bindDenormalizedColumns([
            { name_col: 'pool', model: window.pools, id_col: 'poolid' }
        ])
    },
});

var Slaves = Backbone.Collection.extend({
    url: '/api/slaves',
    model: Slave,

    columns: [
        { id: "name", title: "Name", },
        { id: "distro", title: "Distro", },
        { id: "bitlength", title: "Bits", },
        // omit basedir for space
        //{ id: "basedir", title: "Basedir", },
        { id: "datacenter", title: "DC", },
        { id: "trustlevel", title: "Trust", },
        { id: "environment", title: "Environ", },
        { id: "purpose", title: "Purpose", },
        { id: "pool", title: "Pool", },
        { id: "current_master", title: "Current", },
        { id: "locked_master", title: "Locked", },
        { id: "disabled", title: "Disab", },
    ],
});

//
// Masters
//

var Master = DenormalizedModel.extend({
    initialize: function() {
        this.id = this.get('masterid');

        this.bindDenormalizedColumns([
            { name_col: 'pool', model: window.pools, id_col: 'poolid' }
        ])
    },
});

var Masters = Backbone.Collection.extend({
    url: '/api/masters',
    model: Master,

    columns: [
        { id: "nickname", title: "Nickname", },
        { id: "fqdn", title: "fqdn", },
        { id: "pb_port", title: "PB Port", },
        { id: "http_port", title: "HTTP Port", },
        { id: "datacenter", title: "DC", },
        { id: "pool", title: "Pool", },
    ],
});

//
// ID-to-name models
//

// Note that we do not include everything here, as many of these attributes are
// not editable via the UI

var Pool = Backbone.Model.extend({
    initialize: function() {
        this.id = this.get('poolid');
    },
});

var Pools = Backbone.Collection.extend({
    url: '/api/pools',
    model: Pool,

    // information about the columns in this collection
    columns: [
        { id: "name", title: "Name", },
    ],
});

function initializeModels() {
    window.masters = new Masters();
    window.masters.fetch();

    window.slaves = new Slaves();
    window.slaves.fetch();

    window.pools = new Pools();
    window.pools.fetch();
};
