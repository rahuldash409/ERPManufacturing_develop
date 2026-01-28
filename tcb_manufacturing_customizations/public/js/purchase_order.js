frappe.ui.form.on("Purchase Order", {
    refresh: async function (frm) {
        const service_request_doctype_name = "Service Request";

        if (frm.doc.custom_po_reference &&
            frm.doc.custom_reference_document === service_request_doctype_name) {

            // Hide standard buttons
            setTimeout(() => {
                frm.remove_custom_button("Update Items")
                frm.page.remove_custom_button("Update Items")
                $('button:contains("Update Items")').hide();
                $('button:contains("Get Items From")').hide();
            }, 100);

            if (frm.doc.docstatus === 1) {
                // ✅ Check for draft stock entries
                let draft_entries = await frappe.db.get_list('Stock Entry', {
                    filters: {
                        'custom_another_stock_entry_reference': frm.doc.name,
                        'docstatus': 0
                    },
                    fields: ['name'],
                    limit: 1
                });

                // Show warning if draft exists
                if (draft_entries && draft_entries.length > 0) {
                    let draft_name = draft_entries[0].name;
                    frm.dashboard.set_headline_alert(
                        `<b>⚠️ Draft Stock Entry exists:</b> 
                        <a href="/app/stock-entry/${draft_name}" target="_blank">${draft_name}</a> 
                        - Please submit or cancel it before creating new entries.`,
                        'orange'
                    );
                }

                // Get repair status
                let status = await get_repair_status(frm.doc.name);
                console.log('Repair Status:', status);

                // Show status alert (only if no draft warning)
                if (!draft_entries || draft_entries.length === 0) {
                    show_status_alert(frm, status);
                }

                // Show buttons based on status
                if (status.pending_to_send.length > 0) {
                    frm.add_custom_button(__('Send Spares To Repair'), function () {
                        send_spares_to_repair(frm);
                    }, __('Repair Actions'));
                }

                frm.add_custom_button(__('View Linked Stock Entries'), function () {
                    show_linked_stock_entries(frm);
                }, __('Connections'));

                if (status.sent_but_not_received.length > 0) {
                    frm.add_custom_button(__('Receive Repaired Items'), function () {
                        create_stock_entry_for_repaired_items(frm);
                    }, __('Receive Spares'));

                    frm.add_custom_button(__('Receive And Scrap Spares'), function () {
                        create_permanent_consumption_entry(frm);
                    }, __('Receive Spares'));
                }
            }
        }
    }
});
// Helper: Get repair status
async function get_repair_status(po_name) {
    let response = await frappe.call({
        method: "tcb_manufacturing_customizations.api.purchase_order_api.get_po_repair_status",
        args: { po_name: po_name }
    });
    return response.message;
}

// Helper: Show status alert
function show_status_alert(frm, status) {
    let alert_html = '';
    let alert_color = 'blue';

    if (status.pending_to_send.length > 0) {
        alert_html = `<b>${status.pending_to_send.length} items</b> pending to send for repair (Total: ${status.total_items})`;
        alert_color = 'orange';
    } else if (status.sent_but_not_received.length > 0) {
        alert_html = `<b>${status.sent_but_not_received.length} items</b> sent to repair, pending to receive`;
        alert_color = 'blue';
    } else if (status.received_from_repair === status.total_items) {
        alert_html = `✅ All <b>${status.total_items} items</b> processed (Received/Scrapped)`;
        alert_color = 'green';
    }

    if (alert_html) {
        frm.dashboard.set_headline_alert(alert_html, alert_color);
    }
}

// Helper: Show linked stock entries
function show_linked_stock_entries(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Stock Entry',
            filters: {
                'custom_another_stock_entry_reference': frm.doc.name
            },
            fields: ['name', 'docstatus', 'stock_entry_type', 'creation'],
            order_by: 'creation desc'
        },
        callback: function (r) {
            if (r.message && r.message.length > 0) {
                let html = '<table class="table table-bordered"><thead><tr><th>Stock Entry</th><th>Type</th><th>Status</th><th>Created</th></tr></thead><tbody>';
                r.message.forEach(entry => {
                    let status_badge = '';
                    if (entry.docstatus === 1) {
                        status_badge = '<span class="badge badge-success">Submitted</span>';
                    } else if (entry.docstatus === 2) {
                        status_badge = '<span class="badge badge-danger">Cancelled</span>';
                    } else {
                        status_badge = '<span class="badge badge-warning">Draft</span>';
                    }
                    html += `<tr>
                        <td><a href="/app/stock-entry/${entry.name}" target="_blank">${entry.name}</a></td>
                        <td>${entry.stock_entry_type}</td>
                        <td>${status_badge}</td>
                        <td>${frappe.datetime.str_to_user(entry.creation)}</td>
                    </tr>`;
                });
                html += '</tbody></table>';
                frappe.msgprint({
                    title: __('Linked Stock Entries'),
                    message: html,
                    indicator: 'blue',
                    wide: true
                });
            } else {
                frappe.msgprint(__('No stock entries found'));
            }
        }
    });
}


// Send to Repair (with draft check)
function send_spares_to_repair(frm) {
    // Show loading
    frappe.dom.freeze(__('Checking for existing entries...'));

    // First check for draft entries on client side too
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Stock Entry',
            filters: {
                'custom_another_stock_entry_reference': frm.doc.name,
                'docstatus': 0
            },
            fields: ['name'],
            limit: 1
        },
        callback: function (r) {
            frappe.dom.unfreeze();

            if (r.message && r.message.length > 0) {
                let draft_entry = r.message[0].name;

                frappe.msgprint({
                    title: __('<i class="fa fa-exclamation-triangle"></i> Draft Stock Entry Exists'),
                    message: `
                        <div style="padding: 10px;">
                            <p style="margin-bottom: 15px;">
                                A <b>draft Stock Entry</b> is already created for this Purchase Order.
                            </p>
                            
                            <div style="background: #fff3cd; padding: 12px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #ffc107;">
                                <b>Stock Entry:</b> 
                                <a href="/app/stock-entry/${draft_entry}" target="_blank" style="font-weight: bold; color: #0066cc;">
                                    ${draft_entry}
                                </a>
                            </div>
                            
                            <p style="margin-bottom: 10px;"><b>Please complete one of these actions:</b></p>
                            <ul style="margin-left: 20px; line-height: 1.8;">
                                <li>✅ <b>Submit</b> the draft Stock Entry to complete the transfer</li>
                                <li>❌ <b>Cancel</b> the draft Stock Entry if not needed</li>
                            </ul>
                            
                            <div style="margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px;">
                                <small style="color: #6c757d;">
                                    <i class="fa fa-info-circle"></i> 
                                    You cannot create a new Stock Entry until the existing draft is resolved.
                                </small>
                            </div>
                        </div>
                    `,
                    indicator: 'orange',
                    wide: true
                });

                return;
            }

            // No draft entries, proceed with confirmation
            frappe.confirm(
                __('Send pending spares to Repair Warehouse?<br><br>This will create a Material Transfer Stock Entry.'),
                function () {
                    frappe.dom.freeze(__('Creating Stock Entry...'));

                    frappe.call({
                        method: "tcb_manufacturing_customizations.api.purchase_order_api.send_spares_to_repair_from_po",
                        args: { po_name: frm.doc.name },
                        callback: function (r) {
                            frappe.dom.unfreeze();

                            if (r.message && r.message.stock_entry_name) {
                                frappe.msgprint({
                                    title: __('Stock Entry Created'),
                                    message: __('Stock Entry <b>{0}</b> created with {1} items',
                                        [r.message.stock_entry_name, r.message.items_count]),
                                    indicator: 'green'
                                });

                                frm.reload_doc();

                                setTimeout(() => {
                                    frappe.set_route('Form', 'Stock Entry', r.message.stock_entry_name);
                                }, 1000);
                            } else if (r.message && r.message.message) {
                                frappe.msgprint(r.message.message);
                            }
                        },
                        error: function (r) {
                            frappe.dom.unfreeze();
                        }
                    });
                }
            );
        }
    });
}

// // Receive Repaired Items
// function create_stock_entry_for_repaired_items(frm) {
//     frappe.confirm(
//         __('Receive repaired items back to stock?'),
//         function () {
//             frappe.dom.freeze(__('Creating Stock Entry...'));

//             frappe.call({
//                 method: "tcb_manufacturing_customizations.api.purchase_order_api.create_return_stock_entry_from_po",
//                 args: { po_name: frm.doc.name },
//                 callback: function (r) {
//                     frappe.dom.unfreeze();

//                     if (r.message && r.message.stock_entry_name) {
//                         frappe.msgprint({
//                             title: __('Stock Entry Created'),
//                             message: __('Stock Entry <b>{0}</b> created with {1} items',
//                                 [r.message.stock_entry_name, r.message.items_count]),
//                             indicator: 'green'
//                         });

//                         frm.reload_doc();

//                         setTimeout(() => {
//                             frappe.set_route('Form', 'Stock Entry', r.message.stock_entry_name);
//                         }, 500);
//                     }
//                 }
//             });
//         }
//     );
// }

// // Scrap Items
// function create_permanent_consumption_entry(frm) {
//     frappe.confirm(
//         __('Mark items as unrepairable and scrap them?<br><br><b>Warning:</b> This is permanent.'),
//         function () {
//             frappe.dom.unfreeze(__('Creating Consumption Entry...'));

//             frappe.call({
//                 method: "tcb_manufacturing_customizations.api.purchase_order_api.create_permanent_consumption_from_po",
//                 args: { po_name: frm.doc.name },
//                 callback: function (r) {
//                     frappe.dom.unfreeze();

//                     if (r.message && r.message.stock_entry_name) {
//                         frappe.msgprint({
//                             title: __('Consumption Entry Created'),
//                             message: __('Stock Entry <b>{0}</b> created with {1} items',
//                                 [r.message.stock_entry_name, r.message.items_count]),
//                             indicator: 'orange'
//                         });

//                         frm.reload_doc();

//                         setTimeout(() => {
//                             frappe.set_route('Form', 'Stock Entry', r.message.stock_entry_name);
//                         }, 500);
//                     }
//                 }
//             });
//         }
//     );
// }


// Send to Repair with Dialog
function send_spares_to_repair(frm) {
    frappe.dom.freeze(__('Loading items...'));
    
    // Get available items
    frappe.call({
        method: 'tcb_manufacturing_customizations.api.purchase_order_api.get_items_to_send_for_repair',
        args: { po_name: frm.doc.name },
        callback: function(r) {
            frappe.dom.unfreeze();
            
            if (!r.message || r.message.length === 0) {
                frappe.msgprint(__('No items available to send for repair'));
                return;
            }
            
            show_send_to_repair_dialog(frm, r.message);
        }
    });
}

function show_send_to_repair_dialog(frm, items) {
    let dialog = new frappe.ui.Dialog({
        title: __('Select Items to Send for Repair'),
        size: 'large',
        fields: [
            {
                fieldname: 'instructions',
                fieldtype: 'HTML',
                options: `
                    <div style="padding: 10px; background: #e7f3ff; border-left: 4px solid #2196F3; margin-bottom: 15px;">
                        <b><i class="fa fa-info-circle"></i> Instructions:</b><br>
                        • Select items you want to send for repair<br>
                        • Click on rows to select/deselect<br>
                        • Delete unwanted rows using the delete button<br>
                        • Click <b>Send to Repair</b> when ready
                    </div>
                `
            },
            {
                fieldname: 'items_section',
                fieldtype: 'Section Break',
                label: __('Available Items ({0})', [items.length])
            },
            {
                fieldname: 'items',
                fieldtype: 'Table',
                cannot_add_rows: true,
                cannot_delete_all_rows: false,
                in_place_edit: false,
                data: items.map(item => ({
                    spare_id: item.spare_id,
                    item_code: item.item_code,
                    item_name: item.item_name,
                    serial_no: item.serial_no,
                    workstation: item.workstation,
                    current_warehouse: item.current_warehouse
                })),
                fields: [
                    {
                        fieldname: 'spare_id',
                        fieldtype: 'Link',
                        label: __('Spare ID'),
                        options: 'Workstation Spare Parts',
                        in_list_view: 1,
                        read_only: 1,
                        columns: 2
                    },
                    {
                        fieldname: 'item_code',
                        fieldtype: 'Link',
                        label: __('Item Code'),
                        options: 'Item',
                        in_list_view: 1,
                        read_only: 1,
                        columns: 2
                    },
                    {
                        fieldname: 'serial_no',
                        fieldtype: 'Data',
                        label: __('Serial No'),
                        in_list_view: 1,
                        read_only: 1,
                        columns: 2
                    },
                    {
                        fieldname: 'workstation',
                        fieldtype: 'Link',
                        label: __('Workstation'),
                        options: 'Workstation',
                        in_list_view: 1,
                        read_only: 1,
                        columns: 2
                    },
                    {
                        fieldname: 'current_warehouse',
                        fieldtype: 'Link',
                        label: __('Current Warehouse'),
                        options: 'Warehouse',
                        in_list_view: 1,
                        read_only: 1,
                        columns: 2
                    }
                ]
            }
        ],
        primary_action_label: __('Send to Repair'),
        primary_action: function(values) {
            let selected_items = values.items;
            
            if (!selected_items || selected_items.length === 0) {
                frappe.msgprint(__('Please keep at least one item in the table'));
                return;
            }
            
            let spare_ids = selected_items.map(item => item.spare_id);
            
            frappe.confirm(
                __('Send {0} item(s) to repair warehouse?', [spare_ids.length]),
                function() {
                    dialog.hide();
                    frappe.dom.freeze(__('Creating Stock Entry...'));
                    
                    frappe.call({
                        method: 'tcb_manufacturing_customizations.api.purchase_order_api.send_selected_spares_to_repair',
                        args: {
                            po_name: frm.doc.name,
                            selected_spare_ids: spare_ids
                        },
                        callback: function(r) {
                            frappe.dom.unfreeze();
                            
                            if (r.message && r.message.stock_entry_name) {
                                frappe.msgprint({
                                    title: __('Stock Entry Created'),
                                    message: __('Stock Entry <b>{0}</b> created with {1} items', 
                                        [r.message.stock_entry_name, r.message.items_count]),
                                    indicator: 'green'
                                });
                                
                                frm.reload_doc();
                                
                                setTimeout(() => {
                                    frappe.set_route('Form', 'Stock Entry', r.message.stock_entry_name);
                                }, 1000);
                            }
                        }
                    });
                }
            );
        }
    });
    
    dialog.show();
}


// Receive Repaired Items with Dialog
function create_stock_entry_for_repaired_items(frm) {
    frappe.dom.freeze(__('Loading items...'));
    
    frappe.call({
        method: 'tcb_manufacturing_customizations.api.purchase_order_api.get_items_to_receive_from_repair',
        args: { po_name: frm.doc.name },
        callback: function(r) {
            frappe.dom.unfreeze();
            
            if (!r.message || r.message.length === 0) {
                frappe.msgprint(__('No items available to receive'));
                return;
            }
            
            show_receive_dialog(frm, r.message, 'return');
        }
    });
}


// Scrap Items with Dialog
function create_permanent_consumption_entry(frm) {
    frappe.dom.freeze(__('Loading items...'));
    
    frappe.call({
        method: 'tcb_manufacturing_customizations.api.purchase_order_api.get_items_to_receive_from_repair',
        args: { po_name: frm.doc.name },
        callback: function(r) {
            frappe.dom.unfreeze();
            
            if (!r.message || r.message.length === 0) {
                frappe.msgprint(__('No items available to scrap'));
                return;
            }
            
            show_receive_dialog(frm, r.message, 'scrap');
        }
    });
}


function show_receive_dialog(frm, items, action_type) {
    let title = action_type === 'return' ? 
        __('Select Items to Receive (Repaired)') : 
        __('Select Items to Scrap (Unrepairable)');
    
    let instruction_bg = action_type === 'return' ? '#e7f3ff' : '#fff3cd';
    let instruction_border = action_type === 'return' ? '#2196F3' : '#ffc107';
    
    let dialog = new frappe.ui.Dialog({
        title: title,
        size: 'large',
        fields: [
            {
                fieldname: 'instructions',
                fieldtype: 'HTML',
                options: `
                    <div style="padding: 10px; background: ${instruction_bg}; border-left: 4px solid ${instruction_border}; margin-bottom: 15px;">
                        <b><i class="fa fa-info-circle"></i> Instructions:</b><br>
                        • Items currently in <b>Repair Warehouse</b><br>
                        • Select items you want to ${action_type === 'return' ? 'receive back' : 'scrap'}<br>
                        • Delete unwanted rows<br>
                        ${action_type === 'scrap' ? '<br><b style="color: #d32f2f;"><i class="fa fa-exclamation-triangle"></i> Warning: Scrapped items cannot be recovered!</b>' : ''}
                    </div>
                `
            },
            {
                fieldname: 'items_section',
                fieldtype: 'Section Break',
                label: __('Items in Repair ({0})', [items.length])
            },
            {
                fieldname: 'items',
                fieldtype: 'Table',
                cannot_add_rows: true,
                cannot_delete_all_rows: false,
                in_place_edit: false,
                data: items.map(item => ({
                    spare_id: item.spare_id,
                    item_code: item.item_code,
                    item_name: item.item_name,
                    serial_no: item.serial_no,
                    workstation: item.workstation,
                    current_warehouse: item.current_warehouse
                })),
                fields: [
                    {
                        fieldname: 'spare_id',
                        fieldtype: 'Link',
                        label: __('Spare ID'),
                        options: 'Workstation Spare Parts',
                        in_list_view: 1,
                        read_only: 1,
                        columns: 2
                    },
                    {
                        fieldname: 'item_code',
                        fieldtype: 'Link',
                        label: __('Item Code'),
                        options: 'Item',
                        in_list_view: 1,
                        read_only: 1,
                        columns: 2
                    },
                    {
                        fieldname: 'serial_no',
                        fieldtype: 'Data',
                        label: __('Serial No'),
                        in_list_view: 1,
                        read_only: 1,
                        columns: 2
                    },
                    {
                        fieldname: 'workstation',
                        fieldtype: 'Link',
                        label: __('Workstation'),
                        options: 'Workstation',
                        in_list_view: 1,
                        read_only: 1,
                        columns: 2
                    },
                    {
                        fieldname: 'current_warehouse',
                        fieldtype: 'Link',
                        label: __('Warehouse'),
                        options: 'Warehouse',
                        in_list_view: 1,
                        read_only: 1,
                        columns: 2
                    }
                ]
            }
        ],
        primary_action_label: action_type === 'return' ? __('Receive Items') : __('Scrap Items'),
        primary_action: function(values) {
            let selected_items = values.items;
            
            if (!selected_items || selected_items.length === 0) {
                frappe.msgprint(__('Please keep at least one item in the table'));
                return;
            }
            
            let spare_ids = selected_items.map(item => item.spare_id);
            
            let confirm_msg = action_type === 'return' ?
                __('Receive {0} repaired item(s) back to stock?', [spare_ids.length]) :
                __('Permanently scrap {0} item(s)? This action cannot be undone!', [spare_ids.length]);
            
            frappe.confirm(confirm_msg, function() {
                dialog.hide();
                frappe.dom.freeze(__('Creating Stock Entry...'));
                
                frappe.call({
                    method: 'tcb_manufacturing_customizations.api.purchase_order_api.receive_selected_spares_from_repair',
                    args: {
                        po_name: frm.doc.name,
                        selected_spare_ids: spare_ids,
                        action_type: action_type
                    },
                    callback: function(r) {
                        frappe.dom.unfreeze();
                        
                        if (r.message && r.message.stock_entry_name) {
                            frappe.msgprint({
                                title: __('Stock Entry Created'),
                                message: __('Stock Entry <b>{0}</b> created with {1} items', 
                                    [r.message.stock_entry_name, r.message.items_count]),
                                indicator: action_type === 'return' ? 'green' : 'orange'
                            });
                            
                            frm.reload_doc();
                            
                            setTimeout(() => {
                                frappe.set_route('Form', 'Stock Entry', r.message.stock_entry_name);
                            }, 500);
                        }
                    }
                });
            });
        }
    });
    
    dialog.show();
}
