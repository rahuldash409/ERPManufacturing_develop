frappe.ui.form.on("Asset", {
    refresh: function (frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Manage Repairable Spares'), function () {
                frappe.set_route('List', 'Workstation Spare Parts', {
                    'asset_reference': frm.doc.name
                });
            }, __('Manage Spares Stock'));

            frm.add_custom_button(__('View Service Requests'), function () {
                frappe.set_route('List', 'Service Request', {
                    'asset_reference': frm.doc.name
                });
            }, __('View'));

        }
        if (frm.doc.docstatus === 1) {
            
            // frm.add_custom_button(__('Manage Spares Stock'), function() {
            // }, __('Actions'));
            frm.add_custom_button(__('View Linked Purchase Orders'), function() {
                view_linked_purchase_orders(frm);
            }, __('View'));

            frm.add_custom_button(__('Create Spares Transfer'), function() {
                create_spares_stock_entry(frm, 'Spares Transfer');
            }, __('Manage Spares Stock'));

            frm.add_custom_button(__('Consume Spares'), function() {
                create_spares_stock_entry(frm, 'Spares Consumption');
            }, __('Manage Spares Stock'));

            frm.add_custom_button(__('Return Spares'), function() {
                create_spares_stock_entry(frm, 'Material Transfer');
            }, __('Manage Spares Stock'));
        }
        frm.add_custom_button(__('Asset Warehouse Stock'), () => {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Workstation',
                    filters: { custom_asset: frm.doc.name },
                    fieldname: 'warehouse'
                },
                callback: (r) => {
                    if (r.message && r.message.warehouse) {
                        const warehouse = r.message.warehouse;
                        frappe.set_route('query-report', 'Alliance Spares Balance');
                        setTimeout(() => {
                            if (frappe.query_report) {
                                frappe.query_report.set_filter_value('warehouse', warehouse);
                                frappe.query_report.refresh();
                            }
                        }, 500);
                    } else {
                        frappe.msgprint('No workstation found for this asset');
                    }
                }
            });
        }, __('Inventory'));
        
    }
});

function view_linked_purchase_orders(frm) {
    frappe.call({
        method: 'tcb_manufacturing_customizations.api.asset_api.get_linked_purchase_orders',
        args: {
            asset_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                // Show in dialog with clickable links
                show_po_dialog(r.message, frm);
            } else {
                frappe.msgprint({
                    title: __('No Purchase Orders Found'),
                    message: __('No Purchase Orders are linked to this Asset via Service Requests.'),
                    indicator: 'orange'
                });
            }
        },
        error: function(err) {
            frappe.msgprint({
                title: __('Error'),
                message: __('Failed to fetch linked Purchase Orders.'),
                indicator: 'red'
            });
        }
    });
}

//  Dialog to display POs
function show_po_dialog(po_list, frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Linked Purchase Orders for {0}', [frm.doc.name]),
        size: 'large',
        fields: [
            {
                fieldname: 'po_table',
                fieldtype: 'HTML'
            }
        ],
        primary_action_label: __('Close'),
        primary_action: function() {
            dialog.hide();
        }
    });
    
    // Build table HTML
    let html = `
        <table class="table table-bordered">
            <thead>
                <tr style="background-color: #f8f9fa;">
                    <th style="width: 10%;">#</th>
                    <th style="width: 25%;">Purchase Order</th>
                    <th style="width: 25%;">Service Request</th>
                    <th style="width: 15%;">Status</th>
                    <th style="width: 15%;">Date</th>
                    <th style="width: 10%;">Action</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    po_list.forEach((po, index) => {
        let status_color = po.docstatus === 1 ? 'green' : (po.docstatus === 0 ? 'blue' : 'red');
        let status_text = po.docstatus === 1 ? 'Submitted' : (po.docstatus === 0 ? 'Draft' : 'Cancelled');
        
        html += `
            <tr>
                <td>${index + 1}</td>
                <td>
                    <a href="/app/purchase-order/${po.po_name}" target="_blank">
                        <b>${po.po_name}</b>
                    </a>
                </td>
                <td>
                    <a href="/app/service-request/${po.sr_name}" target="_blank">
                        ${po.sr_name}
                    </a>
                </td>
                <td>
                    <span class="indicator-pill ${status_color}">
                        ${status_text}
                    </span>
                </td>
                <td>${frappe.datetime.str_to_user(po.transaction_date)}</td>
                <td>
                    <button class="btn btn-xs btn-default" onclick="frappe.set_route('Form', 'Purchase Order', '${po.po_name}')">
                        Open
                    </button>
                </td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
        <div style="margin-top: 10px; padding: 10px; background: #e3f2fd; border-left: 4px solid #2196F3;">
            <b><i class="fa fa-info-circle"></i> Total Purchase Orders:</b> ${po_list.length}
        </div>
    `;
    
    dialog.fields_dict.po_table.$wrapper.html(html);
    dialog.show();
}

// function create_spares_stock_entry(frm, stock_entry_type) {
//     frappe.call({
//         method: 'tcb_manufacturing_customizations.api.asset_api.get_warehouses_for_stock_entry',
//         args: {
//             asset_name: frm.doc.name,
//             stock_entry_type: stock_entry_type
//         },
//         callback: function(r) {
//             if (r.message) {
//                 const data = r.message;
                
//                 frappe.model.with_doctype('Stock Entry', function() {
//                     // 
//                     let stock_entry = frappe.model.get_new_doc('Stock Entry');
//                     stock_entry.stock_entry_type = stock_entry_type;
//                     stock_entry.custom_asset_repair = frm.doc.name;
//                     if (stock_entry_type === 'Spares Transfer') {
//                         stock_entry.from_warehouse = data.source_warehouse;
//                         stock_entry.custom_default_workstation = data.workstation;
//                         stock_entry.to_warehouse = data.target_warehouse;
//                         stock_entry.custom_another_stock_entry_reference = frm.doc.name;
//                     } else if (stock_entry_type === 'Spares Consumption') {
//                         stock_entry.from_warehouse = data.source_warehouse;
//                         stock_entry.custom_default_workstation = data.workstation;
//                         stock_entry.target_warehouse = '';
//                         stock_entry.custom_another_stock_entry_reference = frm.doc.name;
//                     } else if (stock_entry_type === 'Material Transfer') {
//                         // console.log('=================data.source warehouse ===================',data.source_warehouse)
//                         // console.log('=================data.target warehouse ===================',data.target_warehouse)
//                         stock_entry.from_warehouse = data.source_warehouse;
//                         stock_entry.to_warehouse = data.target_warehouse;
//                         stock_entry.custom_another_stock_entry_reference = frm.doc.name;
//                         // stock_entry.custom_default_workstation = data.workstation;
//                     }
//                     frappe.set_route('Form', 'Stock Entry', stock_entry.name);
//                 });
//             } else {
//                 frappe.msgprint(__('Unable to fetch warehouse details. Please check if workstation is linked to this asset.'));
//             }
//         },
//         error: function(err) {
//             frappe.msgprint(__('Error fetching warehouse details: ') + err.message);
//         }
//     });
// }

function create_spares_stock_entry(frm, stock_entry_type) {
    frappe.call({
        method: 'tcb_manufacturing_customizations.api.asset_api.get_warehouses_for_stock_entry',
        args: {
            asset_name: frm.doc.name,
            stock_entry_type: stock_entry_type
        },
        callback: function(r) {
            if (r.message) {
                const data = r.message;
                console.log('=================data ===================',data);
                // Set route options
                frappe.route_options = {
                    'stock_entry_type': stock_entry_type,
                    'custom_asset_repair': frm.doc.name,
                    'custom_another_stock_entry_reference': frm.doc.name,
                    // 'custom_default_workstation': data.workstation || '',
                    'from_warehouse': data.source_warehouse,
                    'to_warehouse': data.target_warehouse,
                };
                
                frappe.new_doc('Stock Entry');
                
                // APPLY FILTER AFTER FORM LOADS (1 second delay)
                setTimeout(() => {
                    if (cur_frm && cur_frm.doctype === 'Stock Entry') {
                        if (stock_entry_type === 'Material Transfer') {
                            cur_frm.set_value('custom_default_workstation', "");
                        }
                        else {
                            cur_frm.set_value('custom_default_workstation', data.workstation);
                        }
                        cur_frm.set_value('from_warehouse', data.source_warehouse);
                        cur_frm.set_query('item_code', 'items', function() {
                            return {
                                filters: {
                                    'item_group': ['like', '%spare%']
                                }
                            };
                        });
                        if (stock_entry_type === "Spares Consumption"){
                            cur_frm.set_value('to_warehouse', "");
                        }
                        else{
                            cur_frm.set_value('to_warehouse', data.target_warehouse);
                        }
                        
                        // Optional: Show alert
                        frappe.show_alert({
                            message: __('Filter applied: Only Spare Parts'),
                            indicator: 'blue'
                        }, 2);
                    }
                }, 1000);
                
            } else {
                frappe.msgprint(__('Unable to fetch warehouse details. Please check if workstation is linked to this asset.'));
            }
        },
        error: function(err) {
            frappe.msgprint(__('Error fetching warehouse details: ') + err.message);
        }
    });
}
