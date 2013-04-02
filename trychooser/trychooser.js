$(document).ready(function() {
    // Several subsections are headed by all/none selectors. Make them control
    // their dependents

    // If the all-selector is checked, then force all items to be checked
    var suppress_loop = false;
    $('.all-selector').change(function() {
        if ($(this).attr('checked')) {
            suppress_loop = true;
            $(this).closest('.option-group').find(':checkbox:not(.group-selector)')
                .attr('checked', 1);
            $(this).closest('.option-group').find('.none-selector')
                .removeAttr('checked');
            suppress_loop = false;
        }
    });
    $('.none-selector').change(function() {
        if ($(this).attr('checked')) {
            suppress_loop = true;
            $(this).closest('.option-group').find(':checkbox:not(.group-selector)')
                .removeAttr('checked');
            $(this).closest('.option-group').find('.all-selector')
                .removeAttr('checked');
            suppress_loop = false;
        }
    });

    // Force initial update
    $('.all-selector:checked').change();
    $('.none-selector:checked').change();

    // Make all option-group descendant checkboxes control the group-selectors
    $('.option-group').find(':checkbox:not(.group-selector)').change(function() {
        if (suppress_loop) return;
        // sibs are the "sibling checkboxes", but I can't just use siblings()
        // because they're wrapped in <li> tags.
        var sibs = $(this).closest('.option-group').find(':checkbox:not(.group-selector)');
        if ($(this).attr('checked')) {
            $(this).closest('.option-group').find('.none-selector')
                .removeAttr('checked'); // 'None' is no longer true
            if (sibs.filter(':checked').length == sibs.length) {
                // All are checked. Mark 'All'.
                $(this).closest('.option-group').find('.all-selector')
                    .attr('checked', 1);
            } else {
                $(this).closest('.option-group').find('.all-selector')
                    .removeAttr('checked'); // 'All' is no longer true
            }
        } else {
            $(this).closest('.option-group').find('.all-selector')
                .removeAttr('checked'); // 'All' is no longer true
            if (sibs.filter(':checked').length == 0) {
                // None are checked. Mark 'None'.
                $(this).closest('.option-group').find('.none-selector')
                    .attr('checked', 1);
            }
        }
    });

    // Hacks to handle the mochitests-all subgroup
    $('.subgroup-all-selector').change(function() {
        if ($(this).attr('checked')) {
            $(this).closest('.option-subgroup').find(':checkbox:not(.subgroup-all-selector)')
                .attr('checked', 1);
        }
    });
    $('.option-subgroup').find(':checkbox:not(.subgroup-all-selector)').change(function() {
        var sibs = $(this).closest('.option-subgroup').find(':checkbox:not(.subgroup-all-selector)');
        if ($(this).attr('checked')) {
            if (sibs.filter(':checked').length == sibs.length) {
                // All are checked. Mark 'All'.
                $(this).closest('.option-subgroup').find('.subgroup-all-selector')
                    .attr('checked', 1);
            }
        } else {
            $(this).closest('.option-subgroup').find('.subgroup-all-selector')
                .removeAttr('checked'); // 'All' is no longer true
        }
    });

    $(':checkbox').change(setresult);
    $(':radio').change(setresult);

    setresult();
});

function resolveFilters(filters) {
    // The linux32 hack requires cancelling out mutually-exclusive options
    var want = {};
    for (var i in filters) {
        if (filters[i].charAt(0) != '-') {
            want[filters[i]] = true;
        }
    }
    for (var i in filters) {
        if (filters[i].charAt(0) == '-') {
            var name = filters[i].substring(1);
            if (name in want)
                delete want[name];
            else
                want[filters[i]] = true;
        }
    }
    return Object.keys(want);
}

function setresult() {
    var value = 'try: ';
    var args = [];

    $('.option-radio[try-section]').each(function() {
        var arg = '-' + $(this).attr('try-section') + ' ';
        arg += $(this).find(':checked').attr('value');
        args.push(arg);
    });

    $('.option-email').each(function() {
        var arg = $(this).find(':checked').attr('value');
        if (arg != 'on')
            args.push(arg);
    });

    var have_projects = {};
    $('.option-group[try-section]').each(function() {
        var tryopt = $(this).attr('try-section');
        var arg = '-' + tryopt + ' ';
        var names = [];
        if ($(this).find('.none-selector:checked').length > 0) {
            names = ['none'];
        } else if ($(this).find('.all-selector:checked').length > 0) {
            names = ['all'];
        } else {
            var group = $(this).closest('.option-group');
            var options;
            if (group.find('.subgroup-all-selector:checked').length > 0) {
                // Special-case. We need to collapse things into a subgroup "all" value
                options = group.find(':checked:not(.group-selector):not(.option-subgroup *)')
                    .add('.subgroup-all-selector', group);
            } else {
                options = group.find(':checked:not(.group-selector):not(.subgroup-all-selector)');
            }
            options.each(function(i,elt){
              names.push($(elt).attr('value'));
              var project = $(elt).attr('data-project');
              if (project)
                have_projects[project] = true;
            });
        }

        // If you specifically request a b2g or android build platform, then
        // disable the filtering. This does not apply when you just pick 'all'.
        var disable_filters = ("b2g" in have_projects) || ("android" in have_projects);
        $('[try-filter=' + tryopt + ']').prop('disabled', disable_filters);
        $('[try-filter=' + tryopt + ']').fadeTo(0, disable_filters ? 0.5 : 1.0);

        var filters = [];
        $('[try-filter=' + tryopt + '] :checked').each(function () {
          filters.push.apply(filters, $(this).attr('value').split(','));
        });
        if (filters.length > 0 && !disable_filters) {
          filters = resolveFilters(filters).join(',');
          names = names.map(function (n) { return n + '[' + filters + ']'; });
        }

        arg += names.join(',');
        args.push(arg);
    });

    value = 'try: ' + args.join(' ');

    if ($('#post_to_bugzilla').attr('checked')) {
        value = value + ' --post-to-bugzilla Bug ' + document.getElementById("bugnumber").value;
    }

    if (value.match(/-p none/)) {
        value = "(NO JOBS CHOSEN)";
        $('#platforms-none').addClass('attention');
    } else {
        $('#platforms-none').removeClass('attention');
    }

    $('.result_value').val(value);
}
