$(document).ready(function() {
    //$('#try-options').hide();

    //$('#do_everything').attr('checked', 1); // reset on page refresh

    // Toplevel toggle: do everything, or choose the specifics?
    $('#do_everything').change(function() {
        if ($(this).attr('checked')) {
            $('#try-options').fadeOut();
        } else {
            $('#try-options').fadeIn();
        }
    });

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

function setresult() {
    var label;
    var value;
    if ($('#do_everything').attr('checked')) {
        label = 'Do Everything';
        value = 'try: -b do -p all -u all -t all';
    } else {
        label = 'Other';
        value = 'try: ';
        var args = [];

        $('.option-radio').each(function() {
            var arg = '-' + $(this).attr('try-section') + ' ';
            arg += $(this).find(':checked').attr('value');
            args.push(arg);
        });

        $('.option-email').each(function() {
            var arg = $(this).find(':checked').attr('value');
            if (arg != 'on')
                args.push(arg);
        });

        $('.option-group').each(function() {
            var arg = '-' + $(this).attr('try-section') + ' ';
            if ($(this).find('.none-selector:checked').length > 0) {
                arg += 'none';
            } else if ($(this).find('.all-selector:checked').length > 0) {
                arg += 'all';
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
                var names = [];
                options.each(function(i,elt){ names.push($(elt).attr('value')) });
                arg += names.join(',');
            }
            args.push(arg);
        });
        value = 'try: ' + args.join(' ');
    }

    $('.result_label').text(label);
    $('.result_value').val(value);
}
