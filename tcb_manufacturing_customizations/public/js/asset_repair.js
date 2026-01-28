
async function get_available_items_from_stock_entries(link_field, link_value) {
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
            }
            else if (entry.stock_entry_type === "Spares Consumption") {
                items_data[item_key].qty -= item.qty;
            }
            else if (entry.stock_entry_type === "Material Transfer") {
                items_data[item_key].qty -= item.qty;
            }
            // console.log('=============== Processing Item ===============', item.item_code, 'Qty:', items_data[item_key].qty);
        }
        // console.log('=============== Full Item Data ========000000000=======', items_data);

    }


    // console.log('=============== Items Data===========lllllllllllaaaaaaaaaassssssssttttttt===:', items_data);
    return items_data;
}

async function createAssetStockEntry(stock_entry_type, to_warehouse, from_warehouse, link_value, custom_default_workstation, items_data, link_field) {
    try {
        let stock_entry = frappe.model.get_new_doc('Stock Entry');
        stock_entry.stock_entry_type = stock_entry_type;
        stock_entry[link_field] = link_value;
        // stock_entry.from_warehouse = from_warehouse;
        // stock_entry.to_warehouse = to_warehouse;
        // console.log('==================================== stock_entry ==',stock_entry)

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
            child.use_serial_batch_fields = true


            // console.log('==================================== child ==',child)
            if (item_data.serial_no) {
                child.serial_no = item_data.serial_no;
            }

            if (item_data.custom_select_serial_no) {
                child.custom_select_serial_no = item_data.custom_select_serial_no;
            }

            if (custom_default_workstation) {
                child.custom_workstation = custom_default_workstation;
            }
        })

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


async function fetch_workstation_and_warehouse(asset) {

    let wstn = await frappe.db.get_list('Workstation', {
        filters: {
            custom_asset: asset
        },
        fields: ['name', 'warehouse'],
        limit: 1
    });
    // console.log('============ wstn =', wstn)
    if (!wstn.length) {
        frappe.throw(__('No Workstation found linked with this Asset.'));
        return;
    }
    return {
        workstation_name: wstn[0].name,
        workstation_warehouse: wstn[0].warehouse
    };
}



function check_existing_draft_repairs(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Asset Repair',
            filters: {
                asset: frm.doc.asset,
                docstatus: 0
            },
            fields: ['name'],
            limit: 1
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                frappe.msgprint({
                    title: __('Draft Repair Pending'),
                    message: __('A draft repair <b><a href="/app/asset-repair/{0}">{0}</a></b> already exists for this asset.<br><br>Please submit or cancel it before creating a new one.', 
                        [r.message[0].name]),
                    indicator: 'orange',
                    primary_action: {
                        label: __('Open Existing Draft'),
                        action: function() {
                            frappe.set_route('Form', 'Asset Repair', r.message[0].name);
                        }
                    }
                });
            }
        }
    });
}


frappe.ui.form.on("Asset Repair", {
    asset: function(frm) {
        if (frm.doc.asset && frm.is_new()) {
            check_existing_draft_repairs(frm);
        }
    },
    onload: function(frm) {
        if (frm.is_new() && frm.doc.asset) {
            check_existing_draft_repairs(frm);
        }
    },
    refresh: async function (frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Asset Warehouse Stock'), () => {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Workstation',
                    filters: { custom_asset: frm.doc.asset },
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
            frm.add_custom_button(__('View Spare Parts'), function () {
                frappe.set_route('List', 'Workstation Spare Parts', {
                    'asset_reference': frm.doc.asset
                });
                window.last_window_asset_repair = cur_frm.doc.name

            });
        }
        if (frm.doc.repair_status === "Pending" && !frm.is_new()) {
            frm.add_custom_button(__('Create Spares Transfer'), function () {
                frappe.model.with_doctype('Stock Entry', async function () {
                    let ws = await fetch_workstation_and_warehouse(frm.doc.asset)
                    let stock_entry = frappe.model.get_new_doc('Stock Entry');
                    stock_entry.stock_entry_type = 'Spares Transfer';
                    stock_entry.asset_repair = frm.doc.name;
                    stock_entry.custom_default_workstation = ws.workstation_name;
                    stock_entry.to_warehouse = ws.workstation_warehouse;
                    frappe.set_route('Form', 'Stock Entry', stock_entry.name);
                });
            }, __('Manage Spares Stock'));


            frm.add_custom_button(__('Consume Spares'), async function () {
                frappe.dom.freeze(__('Loading items...'));

                try {
                    const stk_entry_type = "Spares Consumption";
                    const link_field = "asset_repair";
                    const link_value = frm.doc.name;

                    let items_data = await get_available_items_from_stock_entries(link_field, link_value);
                    let ws = await fetch_workstation_and_warehouse(frm.doc.asset);
                    let custom_default_workstation = ws.workstation_name;


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

                    const stock_entry_name = await createAssetStockEntry(
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
            }, __('Manage Spares Stock'));



            frm.add_custom_button(__('Return Spares'), async function () {
                frappe.dom.freeze(__('Loading items...'));

                try {
                    const stk_entry_type = "Material Transfer";
                    const link_field = "asset_repair";
                    const link_value = frm.doc.name;

                    let items_data = await get_available_items_from_stock_entries(link_field, link_value);
                    let ws = await fetch_workstation_and_warehouse(frm.doc.asset);
                    // let custom_default_workstation = ws.workstation_name;
                    let custom_default_workstation = "";
                    let all_returnable_spare_rows = [];

                    for (let item_key in items_data) {
                        let item = items_data[item_key];

                        if ((item.item_group === "Consumable Spares" ||
                            item.item_group === "Store Spares" ||
                            item.item_group === "Repairable Spares") && item.qty > 0) {
                            console.log(' item soruce warehouse =============', item.s_warehouse);
                            console.log(' item target warehouse =============', item.t_warehouse);
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
                    console.log('=================all_returnable_spare_rows ===================', all_returnable_spare_rows)
                    if (!all_returnable_spare_rows.length) {
                        frappe.msgprint({
                            title: __('No Items Available'),
                            message: __('No items available to return'),
                            indicator: 'orange'
                        });
                        return;
                    }

                    frappe.dom.freeze(__('Creating Stock Entry...'));

                    const stock_entry_name = await createAssetStockEntry(
                        stk_entry_type,
                        all_returnable_spare_rows[0].t_warehouse,
                        all_returnable_spare_rows[0].s_warehouse,
                        link_value,
                        custom_default_workstation,
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
            }, __('Manage Spares Stock'));

        }
    }
});
