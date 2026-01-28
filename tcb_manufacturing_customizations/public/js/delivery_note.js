frappe.ui.form.on("Delivery Note", {
    onload_post_render(frm){
        // Ignore these doctypes when cancelling - prevents "Cancel All Documents" popup
        console.log("Before : \n", frm.ignore_doctypes_on_cancel_all);
        frm.ignore_doctypes_on_cancel_all.push("Bales", "Bales Creator", "Stock Entry");
        console.log("After : \n", frm.ignore_doctypes_on_cancel_all);
    },
    refresh: function(frm) {        
        if (frm.doc.docstatus === 0) {
            // Add "Assign Bales" button for row-level bale selection
            frm.add_custom_button(__('Assign Bales to Item'), function() {
                frm.trigger('assign_bales_to_item');
            }, __('Bales'));
        }

        // Add "Show Used Bales" button for all documents (draft, submitted, cancelled)
        if (frm.doc.name) {
            frm.add_custom_button(__('Show Used Bales'), function() {
                frm.trigger('show_used_bales');
            }, __('Bales'));
        }

        // Show bale count in dashboard (fetch from Delivery Note Bales doctype)
        if (frm.doc.name) {
            frappe.call({
                method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales.get_bales_for_delivery_note",
                args: { delivery_note: frm.doc.name },
                async: true,
                callback: function(r) {
                    if (r.message && r.message.total_bales > 0) {
                        frm.dashboard.add_indicator(
                            __('Bales Linked: {0}', [r.message.total_bales]),
                            'blue'
                        );
                    }
                }
            });
        }

    },

    show_used_bales: function(frm) {
        // Show dialog with used bales from Delivery Note Bales doctype
        frappe.call({
            method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales.get_bales_for_delivery_note",
            args: { delivery_note: frm.doc.name },
            callback: function(r) {
                if (!r.message || r.message.bales.length === 0) {
                    frappe.msgprint({
                        title: __('No Bales'),
                        message: __('No bales are linked to this Delivery Note.'),
                        indicator: 'orange'
                    });
                    return;
                }

                show_used_bales_dialog(frm, r.message);
            }
        });
    },

    custom_fetch_bales: async function(frm) {
        // Legacy fetch method - finds bales based on existing DN item batches
        // frappe.show_alert({
        //     message: __('Fetching bales from batches...'),
        //     indicator: 'blue'
        // });

        // await frappe.call({
        //     method: "tcb_manufacturing_customizations.doc_events.delivery_note.refresh_bales_on_batch_change",
        //     args: {
        //         docname: frm.doc.name
        //     },
        //     callback: (r) => {
        //         if (r.message && r.message.bales_added > 0) {
        //             frappe.show_alert({
        //                 message: __('Added {0} bales', [r.message.bales_added]),
        //                 indicator: 'green'
        //             });
        //             frm.reload_doc();
        //         } else {
        //             frappe.show_alert({
        //                 message: __('No new available bales found for the selected batches'),
        //                 indicator: 'orange'
        //             });
        //         }
        //     },
        //     error: () => {
        //         frappe.show_alert({
        //             message: __('Error fetching bales.'),
        //             indicator: 'red'
        //         });
        //     }
        // });
    },

    assign_bales_to_item: async function(frm) {
        // Check if items exist
        if (!frm.doc.items || frm.doc.items.length === 0) {
            frappe.msgprint({
                title: __('No Items'),
                message: __('Please add items to the Delivery Note first.'),
                indicator: 'orange'
            });
            return;
        }

        // Filter items that have item_code and qty
        let valid_items = frm.doc.items.filter(item => item.item_code && item.qty > 0);

        if (valid_items.length === 0) {
            frappe.msgprint({
                title: __('No Valid Items'),
                message: __('Please ensure items have Item Code and Quantity set.'),
                indicator: 'orange'
            });
            return;
        }

        // Filter items that have no bales or partially assigned bales
        let items_needing_bales = [];
        for (let item of valid_items) {
            // Get assigned bales qty for this item row
            let assigned_data = await frappe.call({
                method: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales.get_assigned_bales_qty_for_item',
                args: {
                    delivery_note: frm.doc.name,
                    item_code: item.item_code,
                    dn_item_row_name: item.name
                }
            });

            let assigned_qty = assigned_data.message ? assigned_data.message.assigned_qty : 0;

            // Include item if no bales assigned or partially assigned
            if (assigned_qty < item.qty) {
                items_needing_bales.push({
                    item: item,
                    assigned_qty: assigned_qty,
                    remaining_qty: item.qty - assigned_qty
                });
            }
        }

        if (items_needing_bales.length === 0) {
            frappe.msgprint({
                title: __('All Items Assigned'),
                message: __('All items already have bales fully assigned.'),
                indicator: 'blue'
            });
            return;
        }

        // If only one item needs bales, directly open bale selection
        if (items_needing_bales.length === 1) {
            show_bale_selection_for_item(frm, items_needing_bales[0].item);
            return;
        }

        // Multiple items - show item selection dialog first
        let item_options = items_needing_bales.map(data => {
            let status_label = data.assigned_qty > 0 ?
                ` (${__('Remaining')}: ${frappe.format(data.remaining_qty, {fieldtype: 'Float'})} ${data.item.uom || ''})` :
                '';
            return {
                label: `#${data.item.idx}: ${data.item.item_code} - ${frappe.format(data.item.qty, {fieldtype: 'Float'})} ${data.item.uom || ''}${status_label}`,
                value: data.item.name
            };
        });

        let d = new frappe.ui.Dialog({
            title: __('Select Item Row'),
            fields: [
                {
                    fieldname: 'info',
                    fieldtype: 'HTML',
                    options: `<p class="text-muted">${__('Select the item row to assign bales:')}</p>`
                },
                {
                    fieldname: 'item_row',
                    fieldtype: 'Select',
                    label: __('Item Row'),
                    options: item_options.map(o => o.label).join('\n'),
                    reqd: 1
                }
            ],
            primary_action_label: __('Select Bales'),
            primary_action: function(values) {
                // Extract idx from label format "#1: Item - Qty UOM"
                let selected_label = values.item_row;
                let idx_match = selected_label.match(/^#(\d+):/);
                let selected_idx = idx_match ? parseInt(idx_match[1]) : null;
                let selected_item = frm.doc.items.find(item => item.idx === selected_idx);

                if (selected_item) {
                    d.hide();

                    // Check if bundle already exists
                    if (selected_item.serial_and_batch_bundle) {
                        frappe.confirm(
                            __('This row already has a Serial and Batch Bundle ({0}). Do you want to replace it?',
                                [selected_item.serial_and_batch_bundle]),
                            () => {
                                show_bale_selection_for_item(frm, selected_item);
                            }
                        );
                    } else {
                        show_bale_selection_for_item(frm, selected_item);
                    }
                }
            }
        });

        d.show();
    },

    before_submit: async function(frm) {
        // Validate that bales are linked for segregated items
        let has_segregated = false;

        if (frm.doc.items) {
            for (let item of frm.doc.items) {
                frappe.call({
                    method: "frappe.client.get_value",
                    args: {
                        doctype: "Item",
                        filters: { name: item.item_code },
                        fieldname: "item_group"
                    },
                    async: false,
                    callback: (r) => {
                        if (r.message && r.message.item_group === 'ad*star bags segregated') {
                            has_segregated = true;
                        }
                    }
                });
            }
        }

        if (has_segregated) {
            // Check bales from Delivery Note Bales doctype
            let bales_count = 0;
            await frappe.call({
                method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales.get_bales_for_delivery_note",
                args: { delivery_note: frm.doc.name },
                async: false,
                callback: function(r) {
                    if (r.message) {
                        bales_count = r.message.total_bales || 0;
                    }
                }
            });

            if (bales_count === 0) {
                frappe.msgprint(
                    __('Please add bales before submitting. This delivery contains segregated items.')
                );
                frappe.validated = false;
            }
        }
    }
});

// Row-level bale selection for Delivery Note Item
frappe.ui.form.on('Delivery Note Item', {
    serial_and_batch_bundle: function(frm) {
        if (frm.doc.docstatus === 0) {
            setTimeout(() => {
                frm.trigger('custom_fetch_bales');
            }, 500);
        }
    },

    items_remove: function(frm) {
        if (frm.doc.docstatus === 0) {
            setTimeout(() => {
                frm.trigger('custom_fetch_bales');
            }, 500);
        }
    }
});

/**
 * Show Bale Selection Dialog for a specific DN Item row
 */
async function show_bale_selection_for_item(frm, dn_item_row) {
    // Show loading
    frappe.show_alert({
        message: __('Loading available bales for {0}...', [dn_item_row.item_code]),
        indicator: 'blue'
    });

    // Get already used bales from Delivery Note Bales doctype
    let exclude_bales = [];
    await frappe.call({
        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales.get_bales_for_delivery_note",
        args: { delivery_note: frm.doc.name },
        async: false,
        callback: function(r) {
            if (r.message && r.message.bales) {
                exclude_bales = r.message.bales.map(b => b.bale);
            }
        }
    });

    // Get already assigned qty for this item row
    let assigned_qty_data = { assigned_qty: 0, bales_count: 0 };
    await frappe.call({
        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales.get_assigned_bales_qty_for_item",
        args: {
            delivery_note: frm.doc.name,
            item_code: dn_item_row.item_code,
            dn_item_row_name: dn_item_row.name
        },
        async: false,
        callback: function(r) {
            if (r.message) {
                assigned_qty_data = r.message;
            }
        }
    });

    // Calculate remaining qty
    let dn_item_qty = flt(dn_item_row.qty);
    let assigned_qty = flt(assigned_qty_data.assigned_qty);
    let remaining_qty = dn_item_qty - assigned_qty;

    // Check if all qty already assigned
    if (remaining_qty <= 0) {
        frappe.msgprint({
            title: __('All Qty Already Assigned'),
            message: `<div style="padding: 10px;">
                <table class="table table-bordered" style="margin-bottom: 0;">
                    <tr>
                        <td><strong>${__('Item')}</strong></td>
                        <td>${dn_item_row.item_code}</td>
                    </tr>
                    <tr>
                        <td><strong>${__('DN Item Qty')}</strong></td>
                        <td>${flt(dn_item_qty).toLocaleString()}</td>
                    </tr>
                    <tr>
                        <td><strong>${__('Assigned Qty')}</strong></td>
                        <td style="color: var(--green);">${flt(assigned_qty).toLocaleString()}</td>
                    </tr>
                    <tr>
                        <td><strong>${__('Remaining Qty')}</strong></td>
                        <td style="color: var(--green);">${flt(remaining_qty).toLocaleString()}</td>
                    </tr>
                    <tr>
                        <td><strong>${__('Bales Assigned')}</strong></td>
                        <td>${assigned_qty_data.bales_count}</td>
                    </tr>
                </table>
                <p class="text-muted" style="margin-top: 10px;">
                    ${__('All required qty has been assigned through bales. No more bales needed.')}
                </p>
            </div>`,
            indicator: 'green'
        });
        return;
    }

    // Fetch available bales for this item
    frappe.call({
        method: "tcb_manufacturing_customizations.doc_events.delivery_note.get_bales_for_dn_item",
        args: {
            item_code: dn_item_row.item_code,
            warehouse: dn_item_row.warehouse || null,
            exclude_bales: JSON.stringify(exclude_bales)
        },
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                frappe.msgprint({
                    title: __('No Bales Available'),
                    message: __('No eligible bales found for item {0}. Bales must be in "Packed Import" or "Packed In House" status.',
                        [dn_item_row.item_code]),
                    indicator: 'orange'
                });
                return;
            }

            show_bale_selection_dialog_for_row(frm, dn_item_row, r.message, assigned_qty);
        },
        error: function() {
            frappe.msgprint({
                title: __('Error'),
                message: __('Failed to load available bales. Please try again.'),
                indicator: 'red'
            });
        }
    });
}

/**
 * Show Bale Selection Dialog with table-style layout for a DN item row
 * @param {Object} frm - The form object
 * @param {Object} dn_item_row - The DN item row
 * @param {Array} available_bales - Available bales list
 * @param {Number} already_assigned_qty - Qty already assigned through previous bales
 */
function show_bale_selection_dialog_for_row(frm, dn_item_row, available_bales, already_assigned_qty = 0) {
    // Track selected bales with their qty
    let selected_bales = new Map(); // bale_name -> bale_data

    // DN Item original qty
    let dn_item_qty = flt(dn_item_row.qty);
    // Remaining qty to assign = DN Item Qty - Already Assigned Qty
    let remaining_to_assign = dn_item_qty - flt(already_assigned_qty);

    // Build table HTML
    let table_html = build_bale_table_html_for_row(available_bales);

    // Format numbers for display
    let formatted_dn_qty = flt(dn_item_qty).toLocaleString();
    let formatted_assigned = flt(already_assigned_qty).toLocaleString();
    let formatted_remaining = flt(remaining_to_assign).toLocaleString();

    let d = new frappe.ui.Dialog({
        title: __('Assign Bales to {0}', [dn_item_row.item_code]),
        size: 'extra-large',
        fields: [
            {
                fieldname: 'qty_info',
                fieldtype: 'HTML',
                options: `<div class="qty-summary-box" style="padding: 12px; background: var(--bg-light-gray); border-radius: var(--border-radius); margin-bottom: 15px;">
                    <div class="row">
                        <div class="col-3 text-center">
                            <div class="text-muted" style="font-size: 12px;">${__('DN Item Qty')}</div>
                            <div style="font-size: 18px; font-weight: 600;">${formatted_dn_qty}</div>
                        </div>
                        <div class="col-3 text-center">
                            <div class="text-muted" style="font-size: 12px;">${__('Already Assigned')}</div>
                            <div style="font-size: 18px; font-weight: 600; color: var(--blue);">${formatted_assigned}</div>
                        </div>
                        <div class="col-3 text-center">
                            <div class="text-muted" style="font-size: 12px;">${__('Selected Qty')}</div>
                            <div class="selected-qty" style="font-size: 18px; font-weight: 600; color: var(--primary);">0</div>
                        </div>
                        <div class="col-3 text-center">
                            <div class="text-muted" style="font-size: 12px;">${__('Remaining')}</div>
                            <div class="remaining-qty" style="font-size: 18px; font-weight: 600; color: var(--orange);">${formatted_remaining}</div>
                        </div>
                    </div>
                    <div class="text-center" style="margin-top: 10px; font-size: 13px;">
                        <span class="selected-count">0</span> ${__('of')} ${available_bales.length} ${__('bales selected')}
                    </div>
                </div>`
            },
            {
                fieldname: 'bale_table',
                fieldtype: 'HTML',
                options: table_html
            }
        ],
        primary_action_label: __('Assign Bales'),
        primary_action: function() {
            let selected_list = Array.from(selected_bales.keys());

            if (selected_list.length === 0) {
                frappe.msgprint({
                    title: __('No Selection'),
                    message: __('Please select at least one bale.'),
                    indicator: 'orange'
                });
                return;
            }

            // Calculate total selected qty
            let total_selected = 0;
            selected_bales.forEach(bale => {
                total_selected += bale.total_batch_qty || bale.bale_qty || 0;
            });

            // Warn if partial (selected + already assigned < DN Item qty)
            if (total_selected < remaining_to_assign) {
                frappe.confirm(
                    __('Selected bales ({0}) have less quantity than remaining ({1}). Continue anyway?',
                        [flt(total_selected).toLocaleString(), flt(remaining_to_assign).toLocaleString()]),
                    () => {
                        create_bundle_and_apply(frm, dn_item_row, d, selected_list);
                    }
                );
                return;
            }

            create_bundle_and_apply(frm, dn_item_row, d, selected_list);
        }
    });

    d.show();

    // Attach checkbox handlers after dialog is rendered
    setTimeout(() => {
        attach_checkbox_handlers_for_row(d, available_bales, selected_bales, remaining_to_assign);
    }, 100);
}

/**
 * Build HTML table for bale listing (row-level)
 */
function build_bale_table_html_for_row(bales) {
    let rows_html = bales.map(bale => {
        let status_color = get_status_color(bale.bales_status);
        let bale_qty = bale.total_batch_qty || bale.bale_qty || 0;
        let formatted_qty = flt(bale_qty).toLocaleString();
        return `
            <tr class="bale-row" data-bale="${frappe.utils.escape_html(bale.name)}"
                data-qty="${bale_qty}">
                <td class="text-center" style="width: 40px;">
                    <input type="checkbox" class="bale-checkbox"
                        data-bale="${frappe.utils.escape_html(bale.name)}"
                        data-qty="${bale_qty}">
                </td>
                <td>
                    <a href="/app/bales/${encodeURIComponent(bale.name)}"
                       target="_blank" class="bale-link">
                        ${frappe.utils.escape_html(bale.name)}
                    </a>
                </td>
                <td>${frappe.utils.escape_html(bale.item)}</td>
                <td class="text-right">${formatted_qty}</td>
                <td class="text-center">${bale.batch_count || 0}</td>
                <td>
                    <span class="indicator-pill ${status_color}" style="font-size: 10px !important">
                        ${frappe.utils.escape_html(bale.bales_status)}
                    </span>
                </td>
            </tr>
        `;
    }).join('');

    return `
        <div class="bale-selection-table-wrapper" style="max-height: 350px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: var(--border-radius);">
            <table class="table table-bordered bale-selection-table" style="margin-bottom: 0;">
                <thead style="position: sticky; top: 0; background: var(--bg-color); z-index: 1;">
                    <tr>
                        <th class="text-center" style="width: 40px;">
                            <input type="checkbox" class="select-all-checkbox" title="${__('Select All')}">
                        </th>
                        <th>${__('Bale ID')}</th>
                        <th>${__('Item')}</th>
                        <th class="text-right">${__('Qty')}</th>
                        <th class="text-center">${__('Batches')}</th>
                        <th>${__('Status')}</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows_html}
                </tbody>
            </table>
        </div>
        <style>
            .bale-selection-table tr.selected {
                background-color: var(--highlight-color) !important;
            }
            .bale-selection-table .bale-row:hover {
                background-color: var(--hover-bg-color);
                cursor: pointer;
            }
            .bale-selection-table .bale-link {
                font-weight: 500;
            }
            .bale-selection-table td, .bale-selection-table th {
                vertical-align: middle !important;
                padding: 8px 12px !important;
            }
            .qty-summary-box .h4 {
                margin: 5px 0 0 0;
                font-weight: 600;
            }
        </style>
    `;
}

/**
 * Get indicator color class based on status
 */
function get_status_color(status) {
    const colors = {
        'Packed Import': 'green',
        'Packed In House': 'yellow',
        'Require Packing': 'orange',
        'Need Approval': 'blue',
        'Dispatched': 'purple'
    };
    return colors[status] || 'gray';
}

/**
 * Attach event handlers to checkboxes (row-level version)
 */
function attach_checkbox_handlers_for_row(dialog, bales, selected_bales, target_qty) {
    let $wrapper = dialog.$wrapper;
    let $selectAll = $wrapper.find('.select-all-checkbox');
    let $checkboxes = $wrapper.find('.bale-checkbox');
    let $selectedCount = $wrapper.find('.selected-count');
    let $selectedQty = $wrapper.find('.selected-qty');
    let $remainingQty = $wrapper.find('.remaining-qty');

    // Create bale lookup map
    let baleMap = new Map();
    bales.forEach(b => baleMap.set(b.name, b));

    // Update qty summary display
    function updateQtySummary() {
        let totalQty = 0;
        selected_bales.forEach(bale => {
            totalQty += bale.total_batch_qty || bale.bale_qty || 0;
        });

        let remaining = target_qty - totalQty;

        $selectedCount.text(selected_bales.size);
        $selectedQty.text(flt(totalQty).toLocaleString());
        $remainingQty.text(flt(remaining).toLocaleString());

        // Update color based on remaining
        if (remaining <= 0) {
            $remainingQty.css('color', 'var(--green)');
        } else if (remaining < target_qty * 0.5) {
            $remainingQty.css('color', 'var(--orange)');
        } else {
            $remainingQty.css('color', 'var(--red)');
        }
    }

    // Update select all checkbox state
    function updateSelectAllState() {
        let total = $checkboxes.length;
        let checked = $checkboxes.filter(':checked').length;

        if (checked === 0) {
            $selectAll.prop('checked', false);
            $selectAll.prop('indeterminate', false);
        } else if (checked === total) {
            $selectAll.prop('checked', true);
            $selectAll.prop('indeterminate', false);
        } else {
            $selectAll.prop('checked', false);
            $selectAll.prop('indeterminate', true);
        }
    }

    // Handle individual checkbox change
    $checkboxes.on('change', function() {
        let $checkbox = $(this);
        let bale_name = $checkbox.data('bale');
        let $row = $checkbox.closest('tr');

        if ($checkbox.is(':checked')) {
            let baleData = baleMap.get(bale_name);
            if (baleData) {
                selected_bales.set(bale_name, baleData);
            }
            $row.addClass('selected');
        } else {
            selected_bales.delete(bale_name);
            $row.removeClass('selected');
        }

        updateSelectAllState();
        updateQtySummary();
    });

    // Handle row click to toggle checkbox
    $wrapper.find('.bale-row').on('click', function(e) {
        // Don't toggle if clicking on link or checkbox directly
        if ($(e.target).is('a, input')) return;

        let $checkbox = $(this).find('.bale-checkbox');
        $checkbox.prop('checked', !$checkbox.is(':checked')).trigger('change');
    });

    // Handle select all checkbox
    $selectAll.on('change', function() {
        let is_checked = $(this).is(':checked');

        $checkboxes.each(function() {
            let $checkbox = $(this);
            let bale_name = $checkbox.data('bale');
            let $row = $checkbox.closest('tr');

            $checkbox.prop('checked', is_checked);

            if (is_checked) {
                let baleData = baleMap.get(bale_name);
                if (baleData) {
                    selected_bales.set(bale_name, baleData);
                }
                $row.addClass('selected');
            } else {
                selected_bales.delete(bale_name);
                $row.removeClass('selected');
            }
        });

        updateQtySummary();
    });
}

/**
 * Create Serial Batch Bundle and apply to DN item row
 */
async function create_bundle_and_apply(frm, dn_item_row, dialog, selected_bale_names) {
    // Disable button to prevent double-click
    dialog.get_primary_btn().prop('disabled', true).text(__('Assigning Bales...'));

    try {
        // Save DN first to ensure row name exists
        if (frm.is_dirty()) {
            await frm.save();
        }

        // Assign bales to DN item via API
        let response = await frappe.call({
            method: "tcb_manufacturing_customizations.doc_events.delivery_note.create_serial_batch_bundle_from_bales",
            args: {
                dn_name: frm.doc.name,
                dn_item_row_name: dn_item_row.name,
                item_code: dn_item_row.item_code,
                warehouse: dn_item_row.warehouse,
                company: frm.doc.company,
                bale_names: JSON.stringify(selected_bale_names)
            }
        });

        let result = response.message;

        if (!result || !result.bales_added || result.bales_added.length === 0) {
            frappe.throw(__('Failed to assign bales'));
        }

        // Refresh the form
        frm.refresh_field('items');

        // Close dialog
        dialog.hide();

        // Show success message
        frappe.show_alert({
            message: __('Assigned {0} bales with total qty: {1}',
                [result.bales_added.length, flt(result.total_qty).toLocaleString()]),
            indicator: 'green'
        });

        // Reload form to get updated data
        frm.reload_doc();

    } catch (error) {
        console.error("Error assigning bales:", error);
        frappe.msgprint({
            title: __('Error'),
            message: error.message || __('An unexpected error occurred. Please try again.'),
            indicator: 'red'
        });
        dialog.get_primary_btn().prop('disabled', false).text(__('Assign Bales'));
    }
}

/**
 * Show dialog with all bales linked to this Delivery Note
 */
function show_used_bales_dialog(frm, bales_data) {
    let bales = bales_data.bales;
    let total_bales = bales_data.total_bales;
    let total_qty = bales_data.total_qty;

    // Build table HTML
    let rows_html = bales.map((bale, idx) => {
        let status_color = get_status_color(bale.bales_status);
        let formatted_qty = flt(bale.qty || 0).toLocaleString();
        let remove_btn = frm.doc.docstatus === 0 ?
            `<button class="btn btn-sm btn-danger remove-bale-btn" data-bale="${frappe.utils.escape_html(bale.bale)}" data-item="${frappe.utils.escape_html(bale.item)}">
                <i class="fa fa-trash"></i> Remove
            </button>` :
            '<span class="text-muted">-</span>';

        return `
            <tr data-bale-name="${frappe.utils.escape_html(bale.bale)}">
                <td class="text-center">${idx + 1}</td>
                <td>
                    <a href="/app/bales/${encodeURIComponent(bale.bale)}"
                       target="_blank" class="bale-link">
                        ${frappe.utils.escape_html(bale.bale)}
                    </a>
                </td>
                <td>${frappe.utils.escape_html(bale.item || '')}</td>
                <td class="text-right">${formatted_qty}</td>
                <td class="text-center">${bale.batch_count || 0}</td>
                <td>
                    <span class="indicator-pill ${status_color}" style="font-size: 10px !important; white-space: nowrap;">${frappe.utils.escape_html(bale.bales_status || 'Unknown')}</span>
                </td>
                <td class="text-center">${remove_btn}</td>
            </tr>
        `;
    }).join('');

    let table_html = `
        <div class="bales-summary-box" style="padding: 12px; background: var(--bg-light-gray); border-radius: var(--border-radius); margin-bottom: 15px;">
            <div class="row">
                <div class="col-6 text-center">
                    <div class="text-muted" style="font-size: 12px;">${__('Total Bales')}</div>
                    <div style="font-size: 18px; font-weight: 600; color: var(--primary);">${total_bales}</div>
                </div>
                <div class="col-6 text-center">
                    <div class="text-muted" style="font-size: 12px;">${__('Total Qty')}</div>
                    <div style="font-size: 18px; font-weight: 600;">${flt(total_qty).toLocaleString()}</div>
                </div>
            </div>
        </div>
        <div class="bales-table-wrapper" style="max-height: 400px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: var(--border-radius);">
            <table class="table table-bordered" style="margin-bottom: 0;">
                <thead style="position: sticky; top: 0; background: var(--bg-color); z-index: 1;">
                    <tr>
                        <th class="text-center" style="width: 50px;">#</th>
                        <th>${__('Bale ID')}</th>
                        <th>${__('Item')}</th>
                        <th class="text-right">${__('Qty')}</th>
                        <th class="text-center">${__('Batches')}</th>
                        <th>${__('Status')}</th>
                        <th class="text-center" style="width: 100px;">${__('Actions')}</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows_html}
                </tbody>
            </table>
        </div>
        <style>
            .bales-table-wrapper td, .bales-table-wrapper th {
                vertical-align: middle !important;
                padding: 8px 12px !important;
            }
            .bales-table-wrapper .bale-link {
                font-weight: 500;
            }
        </style>
    `;

    let d = new frappe.ui.Dialog({
        title: __('Used Bales - {0}', [frm.doc.name]),
        size: 'large',
        fields: [
            {
                fieldname: 'bales_table',
                fieldtype: 'HTML',
                options: table_html
            }
        ],
        primary_action_label: __('Close'),
        primary_action: function() {
            d.hide();
        }
    });

    d.show();

    // Add click event handler for remove buttons
    d.$wrapper.find('.remove-bale-btn').on('click', async function(e) {
        e.preventDefault();
        e.stopPropagation();

        let btn = $(this);
        let bale_name = btn.data('bale');
        let item_code = btn.data('item');
        let row = btn.closest('tr');

        // Confirm removal
        frappe.confirm(
            __('Are you sure you want to remove bale {0} from this Delivery Note?', [bale_name]),
            async function() {
                // Disable button during removal
                btn.prop('disabled', true);

                try {
                    // Call backend to remove bale
                    await frappe.call({
                        method: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales.remove_bale_from_delivery_note',
                        args: {
                            delivery_note: frm.doc.name,
                            bale_name: bale_name,
                            item_code: item_code
                        },
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                // Remove row from table
                                row.fadeOut(300, function() {
                                    row.remove();

                                    // Update totals
                                    let remaining_rows = d.$wrapper.find('tbody tr:visible').length;
                                    if (remaining_rows === 0) {
                                        d.hide();
                                        frappe.show_alert({
                                            message: __('All bales removed successfully'),
                                            indicator: 'green'
                                        });
                                    } else {
                                        frappe.show_alert({
                                            message: __('Bale {0} removed successfully', [bale_name]),
                                            indicator: 'green'
                                        });

                                        // Update summary numbers
                                        d.$wrapper.find('.bales-summary-box .col-6:first .font-weight-600').text(r.message.total_bales || remaining_rows);
                                        d.$wrapper.find('.bales-summary-box .col-6:last .font-weight-600').text(flt(r.message.total_qty || 0).toLocaleString());
                                    }
                                });

                                // Refresh form to update item qty
                                frm.reload_doc();
                            }
                        },
                        error: function(err) {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: err.message || __('Failed to remove bale')
                            });
                            btn.prop('disabled', false);
                        }
                    });
                } catch (error) {
                    console.error('Error removing bale:', error);
                    frappe.msgprint({
                        title: __('Error'),
                        indicator: 'red',
                        message: __('Failed to remove bale. Please try again.')
                    });
                    btn.prop('disabled', false);
                }
            },
            function() {
                // User cancelled
                return;
            }
        );
    });
}

