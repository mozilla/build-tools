//
// Parent Classes
//

// A class to view a collection in a DataTables table, with each row
// represented by a TableRowView instance, and with table rows being editable
// via TableRowFormView instances.  The subclass should set this.model in
// initialize before callign the parent method, and should set the rowViewClass
// class variable to the appropriate subclass.  Subclasses can also set
// defaultPageLength to affect pagination.
var TableView = Backbone.View.extend({
    tagName: 'div',
    defaultPageLength: 50, // or 0 to disable pagination

    initialize: function(args) {
        this.editingRow = null; // row currently being edited

        _.bindAll(this, 'refresh', 'render', '_addViewForRow');

        this.model.bind('refresh', this.refresh);
    },

    render: function() {
        // dataTable likes to add sibling nodes, so add the table within
        // the enclosing div, this.el
        $(this.el).append('<table class="display" ' +
            'cellspacing="0" cellpadding="0" border="0"></table>');

        // calculate the columns for the table; this is coordinated with
        // the data for the table in refresh(), below

        // hidden id column
        var aoColumns = [ { bVisible: false } ];
        // data columns
        aoColumns = aoColumns.concat(
            this.model.columns.map(function(col) {
                return { sTitle: col.title, sClass: 'col-' + col.id, };
            }));

        // and un-sortable 'edit' column
        aoColumns.push({
            sTitle: 'Edit',
            bSortable: false,
            fnRender: function () { return '<button class="row-edit"/>'; },
        });

        // create an empty table
        this.dataTable = this.$('table').dataTable({
            aoColumns: aoColumns,
            bJQueryUI: true,
            bPaginate: this.defaultPageLength != 0,
            iDisplayLength: this.defaultPageLength,
            bAutoWidth: false,
        });

        this.refresh();

        return this;
    },

    refresh : function (args) {
        var model = this.model;

        var newData = model.map(function(instance_model) {
            // put the model in the hidden column 0
            var row = [ instance_model.id ];
            // data columns
            row = row.concat(
                _.map(model.columns, function(col) {
                    return instance_model.get(col.id);
                }));
            // and the 'edit' column
            row.push("");
            return row;
        });

        // clear (without drawing) and add the new data
        this.dataTable.fnClearTable(false);
        this.dataTable.fnAddData(newData);
        _.each(this.dataTable.fnGetNodes(), this._addViewForRow );
    },

    _addViewForRow: function (tr) {
        var row = this.dataTable.fnGetData(tr);
        var instance_model = this.model.get(row[0]);
        var view = new this.rowViewClass({
            model: instance_model,
            el: tr,
            dataTable: this.dataTable,
            parentView: this,
        });
        view.render();
    },
});

// A class to represent each row in a TableView; subclasses should set
// editViewClass, but need not do anything else.
var TableRowView = Backbone.View.extend({
    initialize: function(args) {
        this.dataTable = args.dataTable;
        this.parentView = args.parentView;
        this.editView = null;

        _.bindAll(this, 'refresh', 'toggleEdit', 'refreshColumn');

        this.model.bind('change', this.refresh);
    },

    events: {
        'click .row-edit': 'toggleEdit',
    },

    render: function() {
        // note that this.el is set by the parent view
        var edit_button = this.$(".row-edit");
        edit_button.button({ icons: { primary: 'ui-icon-pencil' }, text: false });
        return this;
    },

    refresh: function() {
        _.each(this.parentView.model.columns, this.refreshColumn);
    },

    refreshColumn: function(col) {
        var id = col.id;
        this.$('td.col-' + id).text(this.model.get(id));
    },

    toggleEdit: function(evt) {
        var editingRow = this.parentView.editingRow;
        if (editingRow == this) {
            this.doStopEdit();
        } else {
            if (editingRow) {
                editingRow.doStopEdit();
            }
            this.doStartEdit();
        }

        evt.preventDefault();
    },

    doStopEdit: function() {
        this.dataTable.fnClose(this.el);
        $(this.el).removeClass('row_selected');
        this.parentView.editingRow = null;
        this.editView.remove();
        this.editView = null;
    },

    doStartEdit: function() {
        $(this.el).addClass('row_selected');
        var editRow = this.dataTable.fnOpen(this.el, '', 'editing-row');

        var td = $('td', editRow);
        this.editView = new this.editViewClass({ model: this.model, el: td });
        this.editView.render();

        this.parentView.editingRow = this;
    },
});

// A class to represent the drop-down editing form for a table row.  Subclasses
// should call the parent initialize method from initialize, and should also
// call addFormElements, passing a list of hashes with the following keys:
//  - column: column name this form element represents
//  - title: form element title (used in a <label>)
//  - for: (optional) for reference in the <label>
//  - change: method to call when the model changes
//  - render: method to render the element
// Subclasses are on their own to handle events.
var TableEditRowView = Backbone.View.extend({
    initialize: function(args) {
        _.bindAll(this, 'refresh', 'render');

        this.model.bind('change', this.refresh);
    },

    addFormElements: function(elements) {
        var model = this.model;
        _.each(elements, function(elt) {
            model.bind('change:' + elt.column, elt.change);
        });

        this.formElements = elements;
    },

    render: function() {
        var self = this;
        var el = this.el;

        _.each(this.formElements, function(elt) {
            var div = $('<div/>', { class: 'edit-' + elt.column });
            div.append($('<label/>', { text: elt.title + ': ' }));
            div.append(elt.render.call(self));
            el.append(div);
        });

        this.refresh();

        return this;
    },

    refresh: function() {
        _.each(this.formElements, function(elt) { elt.change(); });
    },
});

//
// View Tabs
//

var ViewTabsView = Backbone.View.extend({
    initialize: function(args) {
        this.viewSpecs = args.viewSpecs;

        _.bindAll(this, 'render');
    },

    render: function() {
        var el = $(this.el);

        _.each(this.viewSpecs, function (viewSpec) {
            // skip views without titles
            if (!viewSpec.title) {
                return;
            }
            var id = 'menu-' + viewSpec.name;
            var input = $('<input/>', {
                type: 'radio',
                name: 'viewmenu',
                id: id,
            });
            input.click(function (elt) {
                window.location.hash = viewSpec.name;
            });

            el.append(input);
            el.append($('<label>', {
                'for': id,
                text: viewSpec.title,
            }));
        });
        el.buttonset();

        return this;
    },
});

//
// Dashboard
//

var DashboardView = Backbone.View.extend({
    tagName: 'div',
    className: 'dashboard',

    initialize: function(args) {
        _.bindAll(this, 'render');
    },

    render: function() {
        $(this.el).text('Select a view.');
        return this;
    },
});

//
// Slaves
//

var SlaveTableRowView = TableRowView.extend({
    editViewClass: null, //SlaveEditRowView,
});

var SlavesTableView = TableView.extend({
    rowViewClass: SlaveTableRowView,
    defaultPageLength: 10,

    initialize: function(args) {
        this.model = window.slaves;

        TableView.prototype.initialize.call(this, args);
    },
});

//
// Masters
//

var MasterEditRowView = TableEditRowView.extend({
    initialize: function(args) {
        TableEditRowView.prototype.initialize.call(this, args);
        _.bindAll(this, 'poolidUpdate', 'poolidChange');

        this.addFormElements([
            { column: 'poolid', title: 'Pool',
              change: this.poolidChange, render: this.poolidRender, }
        ]);
    },

    events: {
        'change select[name="poolid"]': 'poolidUpdate',
    },

    poolidUpdate: function() {
        var newval = parseInt(this.$('select[name="poolid"]').val());
        this.model.set({ poolid: newval });
        this.model.save();
    },

    poolidChange: function() {
        this.$('select[name="poolid"]').val(this.model.get('poolid'));
    },

    poolidRender: function() {
        var select = $('<select/>', { name: 'poolid' });
        window.pools.each(function (pool) {
            var option=$('<option/>', {
                val: pool.id,
                text: pool.get('name'),
            });
            option.appendTo(select);
        });
        return select;
    },
});

var MasterTableRowView = TableRowView.extend({
    editViewClass: MasterEditRowView,
});

var MastersTableView = TableView.extend({
    rowViewClass: MasterTableRowView,
    defaultPageLength: 0,

    initialize: function(args) {
        this.model = window.masters;

        TableView.prototype.initialize.call(this, args);
    },
});

