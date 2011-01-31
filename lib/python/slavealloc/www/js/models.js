//
// Slaves
//

var Slave = Backbone.Model.extend();

var Slaves = Backbone.Collection.extend({
    url: '/api/slaves',
    model: Slave,

    // information about the columns in this collection
    columns: [
        { id: "name", title: "Name", },
        { id: "datacenter", title: "DC", },
        { id: "trustlevel", title: "Trust", },
        { id: "bitlength", title: "Bits", },
        { id: "environment", title: "Environ", },
        { id: "purpose", title: "Purpose", },
        { id: "pool", title: "Pool", },
        { id: "distro", title: "Distro", },
    ],
});

