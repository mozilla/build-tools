//
// Base Classes
//

var DenormalizedModel = Backbone.Model.extend({
    // call this to update denormalized columns (e.g., 'datacenter') to
    // their normalized column ('datacenterid') changes.
    bindDenormalizedColumns: function(column_info) {
        var self = this;

        $.each(column_info, function (i, info) {
            var change_fn = function (model, id) {
                var newname = info.model.get(id).get('name');
                var set = {};
                set[info.name_col] = newname;
                model.set(set);
            };

            self.bind('change:' + info.id_col, change_fn);
        });
    }
});

//
// Slaves
//

var Slave = DenormalizedModel.extend({
    initialize: function() {
        this.id = this.get('slaveid');

        this.bindDenormalizedColumns([
            { name_col: 'pool', model: window.pools, id_col: 'poolid' }
        ]);
    }
});

var Slaves = Backbone.Collection.extend({
    url: '/api/slaves',
    model: Slave
});

//
// Masters
//

var Master = DenormalizedModel.extend({
    initialize: function() {
        this.id = this.get('masterid');

        this.bindDenormalizedColumns([
            { name_col: 'pool', model: window.pools, id_col: 'poolid' }
        ]);
    }
});

var Masters = Backbone.Collection.extend({
    url: '/api/masters',
    model: Master
});

//
// ID-to-name models
//

// Note that we do not include every model here, as many of these attributes
// are not editable via the UI and thus never need to be re-normalized

var Pool = Backbone.Model.extend({
    initialize: function() {
        this.id = this.get('poolid');
    }
});

var Pools = Backbone.Collection.extend({
    url: '/api/pools',
    model: Pool,

    // information about the columns in this collection
    columns: [
        { id: "name", title: "Name" }
    ]
});

window.loadMasters = function(next) {
    window.masters = new Masters();
    window.masters.fetch({ success: next });
    return null;
};

window.loadSlaves = function(next) {
    window.slaves = new Slaves();
    window.slaves.fetch({ success: next });
    return null;
};

window.loadPools = function(next) {
    window.pools = new Pools();
    window.pools.fetch({ success: next });
    return null;
};
