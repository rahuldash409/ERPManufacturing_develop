// File: asset_maintenance_log.js

// ========== HELPER FUNCTIONS (Same as Asset Repair) ==========

async function get_available_items_from_stock_entries(link_field, link_value) {
    // Check for draft entries first
    let draft = await frappe.db.get_list('Stock Entry', {
        filters: {
            docstatus: 0,
            [link_field]: link_value
        },
        fields: ["name"],
        limit: 1
    });
    
    if (draft && draft.length) {
        frappe.throw(`
            <b>Draft Stock Entry Exists!</b><br><br>
            A draft Stock Entry (<b>${draft[0].name}</b>) is already created.<br>
            Please submit or cancel that entry before creating a new one.
        `);
    }

    // Get all submitted stock entries
    let linked_stock_entries = await frappe.db.get_list('Stock Entry', {
        filters: {
            docstatus: 1,
            [link_field]: link_value
        },
        fields: ["name", "stock_entry_type"],
        order_by: 'modified asc',
        limit: 1000
    });

    let items_data = {};

    for (const entry of linked_stock_entries) {
        let stock_items = await frappe.call({
            method: 'tcb_manufacturing_customizations.api.api.get_stock_entry_items',
            args: {
                stock_entry_name: entry.name
            }
        });

        stock_items = stock_items.message;

        for (const item of stock_items) {
            if (!item.item_code) continue;

            let item_key;
            if (item.item_group === "Repairable Spares" && item.serial_no) {
                item_key = `${item.item_code}_${item.serial_no}`;
            } else {
                item_key = item.item_code;
            }

            if (!(item_key in items_data)) {
                items_data[item_key] = {
                    item_code: item.item_code,
                    item_name: item.item_name,
                    qty: 0,
                    uom: item.uom,
                    conversion_factor: item.conversion_factor,
                    transfer_qty: item.transfer_qty,
                    custom_workstation: item.custom_workstation,
                    item_group: item.item_group,
                    s_warehouse: null,
                    t_warehouse: null,
                    serial_no: item.serial_no,
                    custom_select_serial_no: item.custom_select_serial_no,
                    serial_and_batch_bundle: item.serial_and_batch_bundle,
                    custom_stock_item_move_reference: item.custom_stock_item_move_reference,
                };
            }

            // Update quantity based on entry type
            if (entry.stock_entry_type === "Spares Transfer") {
                items_data[item_key].qty += item.qty;
                items_data[item_key].t_warehouse = item.t_warehouse;
                items_data[item_key].s_warehouse = item.s_warehouse;
            } else if (entry.stock_entry_type === "Spares Consumption") {
                items_data[item_key].qty -= item.qty;
            } else if (entry.stock_entry_type === "Material Transfer") {
                items_data[item_key].qty -= item.qty;
            }
        }
    }

    return items_data;
}

async function createMaintenanceStockEntry(stock_entry_type, to_warehouse, from_warehouse, link_value, custom_default_workstation, items_data, link_field) {
    try {
        let stock_entry = frappe.model.get_new_doc('Stock Entry');
        stock_entry.stock_entry_type = stock_entry_type;
        stock_entry[link_field] = link_value;

        if (custom_default_workstation) {
            stock_entry.custom_default_workstation = custom_default_workstation;
        }

        items_data.forEach(item_data => {
            const child = frappe.model.add_child(stock_entry, 'Stock Entry Detail', 'items');
            child.item_code = item_data.item_code;
            child.item_name = item_data.item_name;
            child.item_group = item_data.item_group;
            child.qty = item_data.qty;
            child.transfer_qty = item_data.transfer_qty;
            child.conversion_factor = item_data.conversion_factor;
            child.uom = item_data.uom;
            child.custom_workstation = item_data.custom_workstation;
            child.s_warehouse = item_data.s_warehouse;
            child.t_warehouse = item_data.t_warehouse;
            child.serial_and_batch_bundle = item_data.serial_and_batch_bundle;
            child.custom_stock_item_move_reference = item_data.custom_stock_item_move_reference;
            child.use_serial_batch_fields = true;

            if (item_data.serial_no) {
                child.serial_no = item_data.serial_no;
            }
            if (item_data.custom_select_serial_no) {
                child.custom_select_serial_no = item_data.custom_select_serial_no;
            }
            if (custom_default_workstation) {
                child.custom_workstation = custom_default_workstation;
            }
        });

        frappe.set_route('Form', 'Stock Entry', stock_entry.name);
        frappe.show_alert({
            message: __(`${stock_entry_type} created with ${items_data.length} items`),
            indicator: 'green'
        });

        return stock_entry.name;
    } catch (error) {
        frappe.msgprint(__('Error creating Stock Entry: ' + error.message));
        return null;
    }
}

async function fetch_workstation_and_warehouse_maintenance(asset_name) {
    let result = await frappe.call({
        method: 'tcb_manufacturing_customizations.api.asset_maintenance_api.get_workstation_and_warehouse_for_maintenance',
        args: {
            asset_name: asset_name
        }
    });

    return result.message;
}


// ========== MAIN FORM EVENTS ==========

frappe.ui.form.on("Asset Maintenance Log", {
    
    onload: function(frm) {
        // Auto-fetch asset from Asset Maintenance
        if (frm.doc.asset_maintenance && !frm.doc.asset_name) {
            fetch_asset_from_maintenance(frm);
        }
    },
    
    refresh: async function(frm) {
        
        // Update spares status indicators
        if (!frm.is_new()) {
            update_spares_status(frm);
        }
        
        // Add custom buttons only for submitted logs
        if (frm.doc.asset_name) {
            
            // View Spare Parts button
            frm.add_custom_button(__('View Spare Parts'), function() {
                frappe.set_route('List', 'Workstation Spare Parts', {
                    'asset_reference': frm.doc.asset_name
                });
            }, __('View'));
            
            // View Stock Entries button
            frm.add_custom_button(__('View Stock Entries'), function() {
                frappe.set_route('List', 'Stock Entry', {
                    'custom_another_stock_entry_reference': frm.doc.name
                });
            }, __('View'));
            
            // ========== SPARES MANAGEMENT BUTTONS ==========
            
            // 1. Create Spares Transfer
            frm.add_custom_button(__('Create Spares Transfer'), async function() {
                try {
                    frappe.dom.freeze(__('Fetching warehouse details...'));
                    
                    let ws_data = await fetch_workstation_and_warehouse_maintenance(frm.doc.asset_name);
                    
                    frappe.dom.unfreeze();
                    
                    // Create new Stock Entry
                    frappe.model.with_doctype('Stock Entry', function() {
                        let stock_entry = frappe.model.get_new_doc('Stock Entry');
                        stock_entry.stock_entry_type = 'Spares Transfer';
                        stock_entry.custom_another_stock_entry_reference = frm.doc.name;
                        stock_entry.custom_default_workstation = ws_data.workstation;
                        stock_entry.from_warehouse = ws_data.source_warehouse;
                        stock_entry.to_warehouse = ws_data.target_warehouse;
                        
                        frappe.set_route('Form', 'Stock Entry', stock_entry.name);
                    });
                    
                } catch (error) {
                    frappe.dom.unfreeze();
                    frappe.msgprint(__('Error: ' + error.message));
                }
            }, __('Manage Spares'));
            
            // 2. Consume Spares
            frm.add_custom_button(__('Consume Spares'), async function() {
                frappe.dom.freeze(__('Loading items...'));
                try {
                    const stk_entry_type = "Spares Consumption";
                    const link_field = "custom_another_stock_entry_reference";
                    const link_value = frm.doc.name;
                    
                    let items_data = await get_available_items_from_stock_entries(link_field, link_value);
                    let ws_data = await fetch_workstation_and_warehouse_maintenance(frm.doc.asset_name);
                    let custom_default_workstation = ws_data.workstation;
                    
                    let all_consumable_spare_rows = [];
                    
                    for (let item_key in items_data) {
                        let item = items_data[item_key];
                        
                        if ((item.item_group === "Consumable Spares" ||
                             item.item_group === "Store Spares" ||
                             item.item_group === "Repairable Spares") && item.qty > 0) {
                            
                            all_consumable_spare_rows.push({
                                item_code: item.item_code,
                                item_name: item.item_name,
                                qty: item.qty,
                                uom: item.uom,
                                transfer_qty: item.transfer_qty,
                                conversion_factor: item.conversion_factor,
                                custom_workstation: item.custom_workstation,
                                s_warehouse: item.t_warehouse,
                                t_warehouse: "",
                                serial_no: item.serial_no,
                                custom_select_serial_no: item.custom_select_serial_no,
                                item_group: item.item_group,
                                custom_stock_item_move_reference: item.custom_stock_item_move_reference,
                                serial_and_batch_bundle: item.serial_and_batch_bundle
                            });
                        }
                    }
                    
                    frappe.dom.unfreeze();
                    
                    if (!all_consumable_spare_rows.length) {
                        frappe.msgprint({
                            title: __('No Items Available'),
                            message: __(`
                                <b>No consumable items available</b><br><br>
                                <b>Possible reasons:</b><br>
                                • No Spares Transfer has been created yet<br>
                                • All transferred items have been consumed or returned<br>
                                • No Consumable/Store/Repairable Spares in stock entries
                            `),
                            indicator: 'orange'
                        });
                        return;
                    }
                    
                    const from_warehouse = all_consumable_spare_rows[0].s_warehouse;
                    
                    frappe.dom.freeze(__('Creating Stock Entry...'));
                    const stock_entry_name = await createMaintenanceStockEntry(
                        stk_entry_type,
                        "",
                        from_warehouse,
                        link_value,
                        custom_default_workstation,
                        all_consumable_spare_rows,
                        link_field
                    );
                    frappe.dom.unfreeze();
                    
                    if (!stock_entry_name) {
                        frappe.msgprint("Failed to create Stock Entry");
                    }
                    
                } catch (error) {
                    frappe.dom.unfreeze();
                    frappe.msgprint(__('Error: ' + error.message));
                }
            }, __('Manage Spares'));
            
            // 3. Return Spares
            frm.add_custom_button(__('Return Spares'), async function() {
                frappe.dom.freeze(__('Loading items...'));
                try {
                    const stk_entry_type = "Material Transfer";
                    const link_field = "custom_another_stock_entry_reference";
                    const link_value = frm.doc.name;
                    
                    let items_data = await get_available_items_from_stock_entries(link_field, link_value);
                    let ws_data = await fetch_workstation_and_warehouse_maintenance(frm.doc.asset_name);
                    
                    let all_returnable_spare_rows = [];
                    
                    for (let item_key in items_data) {
                        let item = items_data[item_key];
                        
                        if ((item.item_group === "Consumable Spares" ||
                             item.item_group === "Store Spares" ||
                             item.item_group === "Repairable Spares") && item.qty > 0) {
                            
                            all_returnable_spare_rows.push({
                                item_code: item.item_code,
                                item_name: item.item_name,
                                qty: item.qty,
                                uom: item.uom,
                                transfer_qty: item.transfer_qty,
                                conversion_factor: item.conversion_factor,
                                custom_workstation: item.custom_workstation,
                                s_warehouse: item.t_warehouse,
                                t_warehouse: item.s_warehouse,
                                serial_no: item.serial_no,
                                custom_select_serial_no: item.custom_select_serial_no,
                                item_group: item.item_group,
                                serial_and_batch_bundle: item.serial_and_batch_bundle,
                                custom_stock_item_move_reference: item.custom_stock_item_move_reference
                            });
                        }
                    }
                    
                    frappe.dom.unfreeze();
                    
                    if (!all_returnable_spare_rows.length) {
                        frappe.msgprint({
                            title: __('No Items Available'),
                            message: __('No items available to return'),
                            indicator: 'orange'
                        });
                        return;
                    }
                    
                    frappe.dom.freeze(__('Creating Stock Entry...'));
                    const stock_entry_name = await createMaintenanceStockEntry(
                        stk_entry_type,
                        all_returnable_spare_rows[0].t_warehouse,
                        all_returnable_spare_rows[0].s_warehouse,
                        link_value,
                        "",  // No workstation for returns
                        all_returnable_spare_rows,
                        link_field
                    );
                    frappe.dom.unfreeze();
                    
                    if (!stock_entry_name) {
                        frappe.msgprint("Failed to create Stock Entry");
                    }
                    
                } catch (error) {
                    frappe.dom.unfreeze();
                    frappe.msgprint(__('Error: ' + error.message));
                }
            }, __('Manage Spares'));
        }
    },
    
    // Auto-fetch workstation when Asset Maintenance is selected
    asset_maintenance: function(frm) {
        if (frm.doc.asset_maintenance) {
            fetch_asset_from_maintenance(frm);
        }
    },
    
    // Fetch workstation when asset_name changes
    asset_name: function(frm) {
        if (frm.doc.asset_name) {
            fetch_workstation_and_warehouse(frm);
        }
    }
});

// ========== HELPER FUNCTIONS FOR FORM ==========

function fetch_asset_from_maintenance(frm) {
    frappe.call({
        method: 'tcb_manufacturing_customizations.api.asset_maintenance_api.get_asset_from_maintenance',
        args: {
            asset_maintenance_name: frm.doc.asset_maintenance
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('asset_name', r.message);
                // Also fetch workstation
                fetch_workstation_and_warehouse(frm);
            }
        }
    });
}

function fetch_workstation_and_warehouse(frm) {
    if (!frm.doc.asset_name) return;
    
    frappe.call({
        method: 'tcb_manufacturing_customizations.api.asset_maintenance_api.get_workstation_and_warehouse_for_maintenance',
        args: {
            asset_name: frm.doc.asset_name
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('custom_workstation', r.message.workstation);
                frm.set_value('custom_warehouse', r.message.target_warehouse);
            }
        },
        error: function(err) {
            // Silent fail - workstation might not be linked yet
            console.log('Workstation fetch error:', err);
        }
    });
}

function update_spares_status(frm) {
    frappe.call({
        method: 'tcb_manufacturing_customizations.api.asset_maintenance_api.update_spares_status_for_maintenance',
        args: {
            maintenance_log_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                frm.refresh_field('custom_spares_transferred');
                frm.refresh_field('custom_spares_consumed');
                frm.refresh_field('custom_spares_returned');
                
                // Show status in indicator
                if (r.message.transferred > 0 || r.message.consumed > 0 || r.message.returned > 0) {
                    let status_msg = [];
                    if (r.message.transferred > 0) status_msg.push(`${r.message.transferred} Transfer(s)`);
                    if (r.message.consumed > 0) status_msg.push(`${r.message.consumed} Consumption(s)`);
                    if (r.message.returned > 0) status_msg.push(`${r.message.returned} Return(s)`);
                    
                    frm.dashboard.set_headline_alert(
                        `<b>Spares Activity:</b> ${status_msg.join(' | ')}`,
                        'blue'
                    );
                }
            }
        }
    });
}
