//
// Slaves
//

var SlavesView = Backbone.View.extend({
    tagName: 'div',
    className: 'demo-jui',

    initialize : function (args) {
        this.model = window.slaves;

        _.bindAll(this, 'refresh', 'render');

        this.model.bind('refresh', this.refresh);
    },

    render: function() {
        // dataTable likes to add sibling nodes, so add the table within
        // the enclosing div, this.el
        $(this.el).append('<table class="display" ' +
            'cellspacing="0" cellpadding="0" border="0"></table>');

        // calculate the columns for the table
        var aoColumns = this.model.columns.map(function(col) {
            var rv = { sTitle: col.title };
            return rv;
        });

        // create an empty table
        this.dataTable = this.$('table').dataTable({
            aoColumns: aoColumns,
            bJQueryUI: true,
            bPaginate: false,
            bAutoWidth: false,
        });

        return this;
    },

    refresh : function (args) {
        var model = this.model;

        var newData = model.map(function(slave_model) {
            var row = _.map(model.columns, function(col) {
                return slave_model.get(col.id);
            });
            return row;
        });

        // clear (without drawing) and add the new data
        this.dataTable.fnClearTable(false);
        this.dataTable.fnAddData(newData);
    },
});

//
// Masters
//

var MasterEditView = Backbone.View.extend({
    tagType: 'div',

    initialize: function(args) {
        _.bindAll(this, 'refresh', 'render', 'changePoolid');

        this.model.bind('change', this.refresh);
    },

    events: {
        'change select[name="poolid"]': 'changePoolid',
    },

    changePoolid: function() {
        var newval = parseInt(this.$('select[name="poolid"]').val());
        this.model.set({ poolid: newval });
        this.model.save();
    },

    render: function() {
        var el = $(this.el);

        var label = $('<label/>', { for: 'poolid', text: 'Pool: ' });
        el.append(label)

        var select = $('<select/>', { name: 'poolid' });
        window.pools.each(function (pool) {
            var option=$('<option/>', {
                val: pool.id,
                text: pool.get('name'),
            });
            option.appendTo(select);
        });
        el.append(select);

        this.refresh();

        return this;
    },

    refresh: function() {
        this.$('select[name="poolid"]').val(this.model.get('poolid'));
    },
});

var MasterRowView = Backbone.View.extend({
    initialize: function(args) {
        this.dataTable = args.dataTable;
        this.parentView = args.parentView;
        this.editView = null;

        _.bindAll(this, 'refresh', 'toggleEdit', 'refreshColumn');

        this.model.bind('change', this.refresh);
    },

    events: {
        'click .master-edit': 'toggleEdit',
    },

    render: function() {
        var edit_button = this.$(".master-edit");
        edit_button.button({ icons: { primary: 'ui-icon-pencil' }, text: false });
    },

    refresh: function() {
        _.each(window.masters.columns, this.refreshColumn);
    },

    refreshColumn: function(col) {
        var id = col.id;
        this.$('td.master-' + id).text(this.model.get(id));
    },

    toggleEdit: function(evt) {
        var openRow = this.parentView.openRow;
        if (openRow == this) {
            this.doStopEdit();
        } else {
            if (openRow) {
                openRow.doStopEdit();
            }
            this.doStartEdit();
        }

        evt.preventDefault();
    },

    doStopEdit: function() {
        this.dataTable.fnClose(this.el);
        $(this.el).removeClass('row_selected');
        this.parentView.openRow = null;
        this.editView.remove();
        this.editView = null;
    },

    doStartEdit: function() {
        $(this.el).addClass('row_selected');
        var editRow = this.dataTable.fnOpen(this.el, '', 'open-master-row');

        var td = $('td', editRow);
        this.editView = new MasterEditView({model: this.model});
        td.append(this.editView.render().el);

        this.parentView.openRow = this;
    },
});

var MastersView = Backbone.View.extend({
    tagName: 'div',
    className: 'demo-jui',

    initialize: function (args) {
        this.model = window.masters;
        this.openRow = null; // currently open MasterRowView

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
                return { sTitle: col.title, sClass: 'master-' + col.id, };
            }));

        // and un-sortable 'edit' column
        aoColumns.push({
            sTitle: 'Edit',
            bSortable: false,
            fnRender: function () { return '<button class="master-edit"/>'; },
        });

        // create an empty table
        this.dataTable = this.$('table').dataTable({
            aoColumns: aoColumns,
            bJQueryUI: true,
            bPaginate: false,
            bAutoWidth: false,
        });

        // note that the dataTable isn't added until we've got the data
        return this;
    },

    refresh : function (args) {
        var model = this.model;

        var newData = model.map(function(master_model) {
            // put the model in the hidden column 0
            var row = [ master_model.id ];
            // data columns
            row = row.concat(
                _.map(model.columns, function(col) {
                    return master_model.get(col.id);
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
        var master_model = this.model.get(row[0]);
        var view = new MasterRowView({
            model: master_model,
            el: tr,
            dataTable: this.dataTable,
            parentView: this,
        });
        view.render();
    },
});
