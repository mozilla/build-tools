//
// Parent Classes
//

// A class to view a collection in a DataTables table, with each row
// represented by a TableRowView instance, and with table rows being editable
// via TableRowFormView instances.  The subclass should set this.model in
// initialize before callign the parent method, and should set the rowViewClass
// class variable to the appropriate subclass.  Subclasses can also set
// defaultPageLength to affect pagination.  The 'columns' attribute should be
// a list of coluns to display, giving 'id' (model attribute) and 'title'
// (display name)
var TableView = Backbone.View.extend({
    tagName: 'div',
    defaultPageLength: 50, // or 0 to disable pagination

    initialize: function(args) {
        this.editingRow = null; // row currently being edited

        this.refresh = $.proxy(this, 'refresh');
        this.render = $.proxy(this, 'render');

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
            this.columns.map(function(col) {
                return { sTitle: col.title, sClass: 'col-' + col.id };
            }));

        // and un-sortable 'edit' column
        aoColumns.push({
            sTitle: 'Edit',
            bSortable: false,
            fnRender: function () { return '<button class="row-edit"/>'; }
        });

        // create an empty table
        this.dataTable = this.$('table').dataTable({
            aoColumns: aoColumns,
            bJQueryUI: true,
            bPaginate: this.defaultPageLength !== 0,
            iDisplayLength: this.defaultPageLength,
            bAutoWidth: false
        });

        this.refresh();

        return this;
    },

    refresh : function (args) {
        var self = this;

        var newData = self.model.map(function(instance_model) {
            // put the model in the hidden column 0
            var row = [ instance_model.id ];
            // data columns
            row = row.concat(
                $.map(self.columns, function(col, i) {
                    return instance_model.get(col.id) || '';
                }));
            // and the 'edit' column
            row.push("");
            return row;
        });

        // clear (without drawing) and add the new data
        self.dataTable.fnClearTable(false);
        self.dataTable.fnAddData(newData);
        $.each(self.dataTable.fnGetNodes(), function (i, tr) {
            var row = self.dataTable.fnGetData(tr);
            var instance_model = self.model.get(row[0]);
            var view = new self.rowViewClass({
                model: instance_model,
                el: tr,
                dataTable: self.dataTable,
                parentView: self
            });
            view.render();
        });
    }
});

// A class to represent each row in a TableView; subclasses should set
// editViewClass, but need not do anything else.
var TableRowView = Backbone.View.extend({
    initialize: function(args) {
        this.dataTable = args.dataTable;
        this.parentView = args.parentView;
        this.editView = null;

        this.refresh = $.proxy(this, 'refresh');
        this.toggleEdit = $.proxy(this, 'toggleEdit');

        this.model.bind('change', this.refresh);
    },

    events: {
        'click .row-edit': 'toggleEdit'
    },

    render: function() {
        // note that this.el is set by the parent view
        var edit_button = this.$(".row-edit");
        edit_button.button({ icons: { primary: 'ui-icon-pencil' }, text: false });
        return this;
    },

    refresh: function() {
        var self = this;
        $.each(this.parentView.columns, function (i, col) {
            var id = col.id;
            self.$('td.col-' + id).text(self.model.get(id));
        });
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
        var editRow = this.dataTable.fnOpen(this.el, '', 'edit-row');

        var td = $('td', editRow);
        this.editView = new this.editViewClass({ model: this.model, el: td });
        this.editView.render();

        this.parentView.editingRow = this;
    }
});

// A class to represent the drop-down editing form for a table row.  Subclasses
// should call the parent initialize method from initialize, and should also
// set this.formElements to a list of EditControlView instances.
var TableEditRowView = Backbone.View.extend({
    initialize: function(args) {
        this.render = $.proxy(this, 'render');
    },

    render: function() {
        var self = this;
        var div = $('<div>', { 'class': 'edit-row' });

        $.each(this.formElements, function(i, elt) {
            elt.render();
            div.append(elt.el);
        });

        $(this.el).append(div);
        return this;
    }
});

// A control contained in a TableEditRowView.  List instances of subclasses in
// the formElements attribute of a TableEditRowView instance.  Subclasses
// should implement 'render' and 'modelChanged', and handle events in whatever
// way is suitable.
var EditControlView = Backbone.View.extend({
    tagName: 'div',
    className: 'edit-control',

    defaultColumn: null, // set in subclasses
    defaultTitle: null, // set in subclasses

    initialize: function(args) {
        this.column = args.column || this.defaultColumn;
        this.title = args.title || this.defaultTitle;

        this.model.bind('change:' + this.column,
                        $.proxy(this, 'modelChanged'));
    }
});

// like EditControlView, but with a pre-built render method
// that adds a text element and handles modelChanged and
// controlChanged.  Subclasses need only set defaultTitle
// and defaultColumn
var TextEditControlView = EditControlView.extend({
    events: {
        'change :text': 'controlChanged'
    },

    modelChanged: function() {
        this.$(':text').val(this.model.get(this.column));
    },

    controlChanged: function() {
        var sets = {};
        sets[this.column] = this.$(':text').val();
        this.model.set(sets);
        this.model.save();
    },

    render: function() {
        var el = $(this.el);
        el.append($('<label/>', { text: this.title + ': ' }));

        var input = $('<input/>', { name: this.column });
        el.append(input);

        input.val(this.model.get(this.column));

        return this;
    }
});

// Similarly, an EditControlView that implements a select box, where
// the choices are taken from the collection named in the
// choice_collection argument.
var SelectEditControlView = EditControlView.extend({
    events: {
        'change select': 'controlChanged'
    },

    initialize: function(args) {
        EditControlView.prototype.initialize.call(this, args);

        this.choice_collection = args.choice_collection;
    },

    modelChanged: function() {
        this.$('select').val(this.model.get(this.column));
    },

    controlChanged: function() {
        var sets = {};
        sets[this.column] = parseInt(this.$('select').val(), 10);
        this.model.set(sets);
        this.model.save();
    },

    render: function() {
        var el = $(this.el);
        el.append($('<label/>', { text: this.title + ': ' }));

        var select = $('<select/>', { name: this.column });
        this.choice_collection.each(function (model) {
            var option=$('<option/>', {
                val: model.id,
                text: model.get('name')
            });
            option.appendTo(select);
        });

        el.append(select);

        select.val(this.model.get(this.column));

        return this;
    }
});

//
// Slaves
//

var SlaveEditRowView = TableEditRowView.extend({
    initialize: function(args) {
        TableEditRowView.prototype.initialize.call(this, args);

        this.formElements = [
            new SelectEditControlView({model: this.model,
                    column: 'poolid', title: 'Pool',
                    choice_collection: window.pools }),
            new TextEditControlView({model: this.model,
                    column: 'basedir', title: 'Basedir'})
        ];
    }
});

var SlaveTableRowView = TableRowView.extend({
    editViewClass: SlaveEditRowView
});

var SlavesTableView = TableView.extend({
    rowViewClass: SlaveTableRowView,
    defaultPageLength: 10,

    columns: [
        { id: "name", title: "Name" },
        { id: "distro", title: "Distro" },
        { id: "bitlength", title: "Bits" },
        { id: "basedir", title: "Basedir" },
        { id: "datacenter", title: "DC" },
        { id: "trustlevel", title: "Trust" },
        { id: "environment", title: "Environ" },
        { id: "purpose", title: "Purpose" },
        { id: "pool", title: "Pool" },
        { id: "current_master", title: "Current" },
        { id: "locked_master", title: "Locked" },
        { id: "disabled", title: "Disab" }
    ],

    initialize: function(args) {
        this.model = window.slaves;

        TableView.prototype.initialize.call(this, args);
    }
});

//
// Masters
//

var MasterEditRowView = TableEditRowView.extend({
    initialize: function(args) {
        TableEditRowView.prototype.initialize.call(this, args);

        this.formElements = [
            new TextEditControlView({model: this.model,
                    column: 'nickname', title: 'Nickname'}),
            new TextEditControlView({model: this.model,
                    column: 'fqdn', title: 'FQDN'}),
            new TextEditControlView({model: this.model,
                    column: 'pb_port', title: 'PB Port'}),
            new TextEditControlView({model: this.model,
                    column: 'http_port', title: 'HTTP Port'}),
            new SelectEditControlView({model: this.model,
                    column: 'poolid', title: 'Pool',
                    choice_collection: window.pools })
        ];
    }
});

var MasterTableRowView = TableRowView.extend({
    editViewClass: MasterEditRowView
});

var MastersTableView = TableView.extend({
    rowViewClass: MasterTableRowView,
    defaultPageLength: 0,

    columns: [
        { id: "nickname", title: "Nickname" },
        { id: "fqdn", title: "fqdn" },
        { id: "pb_port", title: "PB Port" },
        { id: "http_port", title: "HTTP Port" },
        { id: "datacenter", title: "DC" },
        { id: "pool", title: "Pool" }
    ],

    initialize: function(args) {
        this.model = window.masters;

        TableView.prototype.initialize.call(this, args);
    }
});

//
// View Tabs
//

var ViewTabsView = Backbone.View.extend({
    initialize: function(args) {
        this.viewSpecs = args.viewSpecs;

        this.render = $.proxy(this, 'render');
    },

    render: function() {
        var el = $(this.el);

        $.each(this.viewSpecs, function (i, viewSpec) {
            // skip views without titles
            if (!viewSpec.title) {
                return;
            }
            var id = 'menu-' + viewSpec.name;
            var input = $('<input/>', {
                type: 'radio',
                name: 'viewmenu',
                id: id
            });
            input.click(function (elt) {
                window.location.hash = viewSpec.name;
            });

            el.append(input);
            el.append($('<label>', {
                'for': id,
                text: viewSpec.title
            }));
        });
        el.buttonset();

        return this;
    }
});

//
// Dashboard
//

var DashboardView = Backbone.View.extend({
    tagName: 'div',
    className: 'dashboard',

    initialize: function(args) {
        this.render = $.proxy(this, 'render');
    },

    render: function() {
        $(this.el).text('Select a view.');
        return this;
    }
});

