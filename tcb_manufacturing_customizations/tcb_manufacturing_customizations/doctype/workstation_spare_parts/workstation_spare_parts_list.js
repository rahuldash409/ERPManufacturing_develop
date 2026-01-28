
async function process_service_request_creation(values, dialog, listview, last_window_asset_repair) {
    await validate_required_table_fields(
        dialog,
        "spares_details_for_stock_entry",
        values.spares_details_for_stock_entry
    );
    // console.log('===== last window asset repari====', last_window_asset_repair);
    let entry_date = values.default_repair_start_date;
    let suppliers = {};
    let sr_item_history_map = {};  
    // Group by supplier
    values.spares_details_for_stock_entry.forEach(row => {
        const sup = row.repair_responsible_party;
        if (!suppliers[sup]) suppliers[sup] = [];
        suppliers[sup].push(row);
    });

    const payload = [];
    for (const sup in suppliers) {
        payload.push({
            supplier: sup,
            schedule_date: entry_date,
            asset_repair_reference: last_window_asset_repair,
            rows: suppliers[sup]
        });
    }

    try {
        freeze_ui('Creating Service Requests...');

        // Step 1: Create SRs and map rows to SR items
        for (const p of payload) {
            let result = await frappe.call({
                method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_service_request_for_supplier",
                args: { data: p }
            });

            if (result.message && result.message.sr_name) {
                let sr_name = result.message.sr_name;
                
                // Fetch SR doc to get child table structure
                let sr_doc = await frappe.db.get_doc("Service Request", sr_name);
                
                // Initialize map for this SR
                if (!sr_item_history_map[sr_name]) {
                    sr_item_history_map[sr_name] = {};
                }
                
                // Map each spare_part to its child table row index
                sr_doc.service_request_item_details.forEach((item_row, idx) => {
                    sr_item_history_map[sr_name][item_row.linked_item] = {
                        idx: idx,
                        row_name: item_row.name,
                        histories: []
                    };
                });
                
                // Store SR name in payload rows for later use
                p.rows.forEach(row => {
                    row._sr_name = sr_name;
                });
            }
        }

        // Step 2: Create Move Histories and collect them
        for (const row of values.spares_details_for_stock_entry) {
            let spare_entry_doc = await frappe.db.get_doc("Workstation Spare Parts", row.line_id);
            
            let move_history_data = {
                spare_entry_reference: row.line_id,
                workstation: spare_entry_doc.workstation,
                spare_part: row.spare_part,
                from_warehouse: row.source_warehouse,
                to_warehouse: row.target_warehouse,
                entry_date: entry_date,
                old_status: spare_entry_doc.spare_status,
                current_status: "Sent For Repair",
                item_serial_number: row.serial_no,
                service_request_reference: row._sr_name,
                asset_repair_reference: last_window_asset_repair,
                asset_reference: row.asset,
                entry_details: `Spare (${row.spare_part}) sent for repair via SR: ${row._sr_name}`
            };

            let history_result = await frappe.call({
                method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
                args: { data: move_history_data }
            });

            if (history_result.message) {
                let sr_name = row._sr_name;
                let spare_part = row.spare_part;
                
                // Push history to correct SR item
                if (sr_item_history_map[sr_name] && sr_item_history_map[sr_name][spare_part]) {
                    sr_item_history_map[sr_name][spare_part].histories.push(history_result.message);
                }
            }
        }

        // Step 3: Update each SR's child table items with move histories
        for (const sr_name in sr_item_history_map) {
            let items_map = sr_item_history_map[sr_name];
            
            for (const spare_part in items_map) {
                let item_data = items_map[spare_part];
                
                if (item_data.histories.length > 0) {
                    // Update child table row
                    await frappe.call({
                        method: "frappe.client.set_value",
                        args: {
                            doctype: "Service Request Detail",
                            name: item_data.row_name,
                            fieldname: "spare_move_history_names",
                            value: item_data.histories.join("\n")
                        }
                    });
                }
            }
        }
        // Refresh listview to show updated records
        // If there is only one SR created, open it directly   
        if (Object.keys(sr_item_history_map).length === 1) {
            const sole_sr_name = Object.keys(sr_item_history_map)[0];
            frappe.set_route("Form", "Service Request", sole_sr_name);
        } else {
            listview.refresh();
        }
        unfreeze_ui();
        frappe.msgprint({
            title: __('Success'),
            message: __('Service Request(s) and Move Histories created successfully'),
            indicator: 'green'
        });

        dialog.hide();

    } catch (err) {
        unfreeze_ui();
        console.error(err);
        frappe.throw(__("Failed to create Service Request(s): ") + err.message);
    }
}



function validate_required_table_fields(dialog, table_fieldname, values) {
    const table_def = dialog.fields_dict[table_fieldname].df.fields;
    const required_cols = table_def.filter(col => col.reqd);

    values.forEach((row, idx) => {
        required_cols.forEach(col => {
            if (!row[col.fieldname]) {
                frappe.throw(`Row ${idx+1}: <b>${col.label}</b> is required.`);
            }
        });
    });
}


// Reusable function for syncing parent field to child table rows
function add_sync_field_to_child_table(dialog, parent_field_config, child_table_fieldname, child_field_mappings) {
    /**
     * @param {Object} dialog - frappe.ui.Dialog instance
     * @param {Object} parent_field_config - Parent field configuration
     *   Example: { fieldname: 'default_date', label: 'Default Repair Start Date', fieldtype: 'Date' }
     * @param {String} child_table_fieldname - Child table fieldname in dialog
     * @param {Array} child_field_mappings - Array of mappings between parent and child fields
     *   Example: [
     *     { parent: 'default_date', child: 'repair_start_date' },
     *     { parent: 'default_warehouse', child: 'target_warehouse' },
     *     { parent: 'default_party', child: 'repair_responsible_party' }
     *   ]
     */
    
    // Find the child table field
    let child_table_field = dialog.fields_dict[child_table_fieldname];
    
    if (!child_table_field) {
        console.error(`Child table field '${child_table_fieldname}' not found in dialog`);
        return;
    }
    
    // Find which child field to update for this parent
    let mapping = child_field_mappings.find(m => m.parent === parent_field_config.fieldname);
    
    if (!mapping) {
        console.error(`No mapping found for parent field '${parent_field_config.fieldname}'`);
        return;
    }
    
    // Get parent field
    let parent_field = dialog.fields_dict[parent_field_config.fieldname];
    
    if (!parent_field) {
        console.error(`Parent field '${parent_field_config.fieldname}' not found in dialog`);
        return;
    }
    
    // Add change handler based on field type
    if (parent_field_config.fieldtype === 'Date') {
        // For Date fields, use $input.on('change')
        parent_field.$input.on('change', function() {
            let parent_value = dialog.get_value(parent_field_config.fieldname);
            
            // Update all rows in child table
            let child_table_data = dialog.get_value(child_table_fieldname) || [];
            
            child_table_data.forEach(row => {
                row[mapping.child] = parent_value;
            });
            
            // Refresh the child table
            child_table_field.grid.refresh();
        });
    } else if (parent_field_config.fieldtype === 'Link') {
        // For Link fields, use df.onchange
        parent_field.df.onchange = function() {
            let parent_value = dialog.get_value(parent_field_config.fieldname);
            
            // Update all rows in child table
            let child_table_data = dialog.get_value(child_table_fieldname) || [];
            
            child_table_data.forEach(row => {
                row[mapping.child] = parent_value;
            });
            
            // Refresh the child table
            child_table_field.grid.refresh();
        };
    } else {
        // For other field types, use $input.on('change')
        parent_field.$input.on('change', function() {
            let parent_value = dialog.get_value(parent_field_config.fieldname);
            
            // Update all rows in child table
            let child_table_data = dialog.get_value(child_table_fieldname) || [];
            
            child_table_data.forEach(row => {
                row[mapping.child] = parent_value;
            });
            
            // Refresh the child table
            child_table_field.grid.refresh();
        });
    }
}


function settings_not_found_validation_check(abbreviation){
    frappe.throw({
                    title: `${abbreviation} Missing`,
                    message: `
                        <b>${abbreviation} is not configured!</b><br><br>
                        Please set the <b>${abbreviation}</b> in the 
                        <b>Workstation Spares Settings</b> before performing this action.<br>
                        👉 <a href="/app/workstation-spares-settings/Workstation%20Spares%20Settings" 
                            target="_blank" 
                            style="font-weight:600; color:#2980b9;">
                                Open Workstation Spares Settings
                            </a>
                    `
                });
}

function freeze_ui(msg = "Processing... Please wait") {
    frappe.dom.freeze(msg);
}

function unfreeze_ui() {
    frappe.dom.unfreeze();
}

async function check_spare_history_and_stock_entry (selected_rows_names_list,all_selected_docs){
try {
                    // let spare_doc = await frappe.db.get_doc("Workstation Spare Parts", selected_row.name)
                    let spare_doc_list = await frappe.db.get_list("Workstation Spare Parts",{
                        fields:["*"],
                        filters: {
                            'name': ['in',selected_rows_names_list]
                        },
                    })
                    // if (spare_doc_list.length > 0){
                    //     let spare_doc_list_names = []
                    //     for (sd of spare_doc_list){
                    //         spare_doc_list_names.push(sd.name)
                    //     }
                    //     console.log('===== here is the spare_doc_list_names  = ', spare_doc_list_names)
                    // }
                    let move_history_list = await frappe.db.get_list("Spares Move History", {
                        fields: ['*'],
                        filters: {
                            'spare_entry_reference': ['in',selected_rows_names_list]
                        },
                        order_by: "creation desc"
                    });

                    for (const spare_doc of spare_doc_list){
                    spare_doc['move_histories'] = []
                        
                    for (const history of move_history_list){
                    // console.log('-------------------strat of the for =====' )
                        if (history.spare_entry_reference==spare_doc.name){
                            // console.log('-=============ififfff========',history.spare_entry_reference)
                            spare_doc.move_histories.push(history.name)
                            // console.log('------------------- spare doc move hitoryes --', spare_doc.move_histories)
                        }
                    }
                    if (!spare_doc.move_histories.length) {
                        frappe.msgprint(`No move history found for Spare: <b>${spare_doc.name}</b>`);
                        return;
                    }
                    let latest_history = move_history_list[0];
                    // const r = await frappe.db.get_value(
                    //     'Stock Entry',
                    //     latest_history.stock_entry_reference,
                    //     'docstatus'
                    // );
                    // if (!r.message) {
                    //     frappe.msgprint("Failed to fetch Docstatus of Stock Entry!");
                    //     return;
                    // }

                    // let docstatus = r.message.docstatus;

                    // if (docstatus == 0) {
                    //     frappe.msgprint(`
                    //             <b>Stock Entry Not Submitted!</b><br><br>
                    //             Spare Entry: <b>${spare_doc.name}</b><br>
                    //             Stock Entry: <b>${latest_history.stock_entry_reference}</b><br><br>
                    //             This Stock Entry is not submitted yet. Please submit it first or Cancel it.
                    //         `);
                    //     return;
                    // }
                    if (latest_history.current_status === "Sent For Repair" && !latest_history.is_service_request_submitted && !latest_history.is_service_request_rejected) {
                        frappe.throw(`
                                <b>Service Request Not Submitted!</b><br><br>
                                Spare Entry: <b>${spare_doc.name}</b><br>
                                Service Request: <b>${latest_history.service_request_reference}</b><br><br>
                                This Service Request is not submitted yet. Please submit it first or Cancel it.
                            `);
                            return;
                        }
                        
                        //  Now check the repair_po_reference field if exists not exists this feild then give error of PO not created yet, 
                    //  And if exists then check this get doc this PO and check its submitte or not.
                    
                    if (latest_history.current_status === "Sent For Repair" && !latest_history.repair_po_reference && !latest_history.is_service_request_rejected) {
                        frappe.throw(`
                            <b>Purchase Order Not Created!</b><br><br>
                            Spare Entry: <b>${spare_doc.name}</b><br>
                            Service Request: <b>${latest_history.service_request_reference}</b><br><br>
                            No Purchase Order has been created yet for this Service Request. Please create a PO first.
                        `);
                        return;
                    }

                    if (latest_history.repair_po_reference && !latest_history.is_service_request_rejected) {
                        const po_result = await frappe.db.get_value(
                            'Purchase Order',
                            latest_history.repair_po_reference,
                            'docstatus'
                        );
                        
                        if (!po_result.message) {
                            frappe.msgprint("Failed to fetch Docstatus of Purchase Order!");
                            return;
                        }

                        let po_docstatus = po_result.message.docstatus;

                        if (po_docstatus !== 1) {
                            frappe.throw(`
                                <b>Purchase Order Not Submitted!</b><br><br>
                                Spare Entry: <b>${spare_doc.name}</b><br>
                                Purchase Order: <b>${latest_history.repair_po_reference}</b><br><br>
                                This Purchase Order is not submitted yet. Please submit it first.
                            `);
                            return;
                        }
                    }
                    // if (latest_history.current_status === "Sent For Repair" && !latest_history.repair_po_reference && !latest_history.is_service_request_rejected) {
                    //     frappe.throw(`
                    //             <b>Service Request Not Submitted!</b><br><br>
                    //             Spare Entry: <b>${spare_doc.name}</b><br>
                    //             Service Request: <b>${latest_history.service_request_reference}</b><br><br>
                    //             This Service Request is not submitted yet. Please submit it first or Cancel it.
                    //         `);
                    //         return;
                    //     }
                        if (!latest_history.is_stock_entry_submitted && !latest_history.is_service_request_rejected) {
                            frappe.throw(`
                                    <b>Stock Entry Not Submitted!</b><br><br>
                                    Spare Entry: <b>${spare_doc.name}</b><br>
                                    Stock Entry: <b>${latest_history.stock_entry_reference}</b><br><br>
                                    This Stock Entry is not submitted yet. Please submit it first or Cancel it.
                                `);
                            return;
                        }
                    // console.log("Stock Entry submitted, proceed:", latest_history);
                    let serial_no_doc = await frappe.db.get_doc("Serial No", spare_doc.item_serial_number)
                    if (latest_history.to_warehouse != serial_no_doc.warehouse){
                        frappe.throw(`
                                <b>Warehouse Mismatch Detected</b><br><br>
                                The selected spare's serial number is currently located in 
                                <b>${serial_no_doc.warehouse}</b>, but the system expected it to be in 
                                <b>${latest_history.to_warehouse}</b> based on the last movement record.<br><br>
                                Please verify the serial number movement or correct the warehouse before proceeding.
                            `);
                        return;
                    }
                    else {
                        spare_doc.source_warehouse = serial_no_doc.warehouse
                        all_selected_docs.push(spare_doc)
                        }
                        // console.log('inside teh loop yeeey-- here is the all_selected_docs ==',spare_doc.source_warehouse)    
                    }
                    return all_selected_docs
                } catch (error) {
                    console.error('Error fetching doc:', error);
                    return;
                }
            }


frappe.listview_settings['Workstation Spare Parts'] = {
    filters: [
        ['spare_status', '=', 'In Use'],
    ]
    ,
    onload:async function (listview) {
        // console.log('========================== window last name ----', window.last_name)
        const last_window_asset_repair = window.last_window_asset_repair
        // const repair_warehouse_name = "Repair Warehouse - APUI"
        const spares_settings_doc = await frappe.db.get_doc('Workstation Spares Settings','Workstation Spares Settings',);
        const repair_warehouse_name =  spares_settings_doc.default_repair_warehouse_for_repairables
        const today_date = frappe.datetime.get_today()
        const repairable_storage_warehouse_name =  spares_settings_doc.default_storage_warehouse_for_repairables
        const damaged_warehouse = spares_settings_doc.default_damaged_items_warehouse
        // console.log('hererere====== repair awarehousenaem --',spares_settings_doc.default_repair_warehouse_for_repairables)

        // let list = frappe.db.get_list("Spares Move History", {fields: ['*'],filters:{
        //     'name':"Dynaflex-DNFLX_SPR445-Installation Pending-304"
        // }, limit: 20})
        // console.log(
        //     'hereeeee ',list
        // )
        // console.log(
        //     'hereeeee '
        // )



let send_for_repair_btn = listview.page.add_action_item(__("Generate Repair Service Request"), async () => {
    if (!repair_warehouse_name){
        frappe.throw({
            title: "Repair Warehouse Missing",
            message: `
                <b>Default Repair Warehouse is not configured!</b><br><br>
                Please set the <b>Default Repair Warehouse</b> in the 
                <b>Workstation Spares Settings</b> before performing this action.<br>
                👉 <a href="/app/workstation-spares-settings/Workstation%20Spares%20Settings" 
                    target="_blank" 
                    style="font-weight:600; color:#2980b9;">
                    Open Workstation Spares Settings
                </a>
            `
        });
        return;
    }

    let selected_rows_names = listview.get_checked_items();
    let all_selected_docs = []
    let selected_rows_names_list = []
    
    for (const selected_row of selected_rows_names) {
        selected_rows_names_list.push(selected_row.name)
    }
    
    await check_spare_history_and_stock_entry(selected_rows_names_list, all_selected_docs)
    
    const spare_table_data = all_selected_docs.map(row_doc => {
        return {
            source_warehouse: row_doc.source_warehouse,
            target_warehouse: repair_warehouse_name,
            spare_part: row_doc.spare_part,
            line_id: row_doc.name,
            serial_no: row_doc.item_serial_number,
            asset: row_doc.asset_reference,
        };
    })
    
    let d = new frappe.ui.Dialog({
        title: 'Enter Spare Details: SR Creation',
        size: 'extra-large',
        fields: [
            {
                label: 'Default Repair Start Date',
                fieldname: 'default_repair_start_date',
                fieldtype: 'Date',
                reqd: 1, 
                description: 'This date will be applied to all rows below',
                default: today_date
            },
            {
                label: 'Default Target Warehouse',
                fieldname: 'default_target_warehouse',
                fieldtype: 'Link',
                options: 'Warehouse',
                description: 'This warehouse will be applied to all rows below',
                default: repair_warehouse_name,
                get_query: () => ({
                    filters: { name: ['like', '%repair%'] }
                })
            },
            {
                label: 'Default Repair Responsible Party',
                fieldname: 'default_repair_responsible_party',
                fieldtype: 'Link',
                options: 'Supplier',
                description: 'This party will be applied to all rows below'
            },
            {
                fieldname: 'column_break_1',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'section_break_1',
                fieldtype: 'Section Break',
                label: 'Spares Details'
            },
            {
                label: 'Spares Details For Stock Entry',
                fieldname: 'spares_details_for_stock_entry',
                fieldtype: 'Table',
                cannot_add_rows: true,
                in_place_edit: true,
                data: spare_table_data,
                reqd: 1,
                fields: [
                    { 
                        label: 'Source Warehouse', 
                        fieldname: 'source_warehouse', 
                        fieldtype: 'Link', 
                        options: 'Warehouse', 
                        in_list_view: 1, 
                        width: 150, 
                        reqd: 1, 
                        read_only: true 
                    },
                    {
                        label: 'Target Warehouse', 
                        fieldname: 'target_warehouse', 
                        fieldtype: 'Link', 
                        options: 'Warehouse', 
                        in_list_view: 1, 
                        reqd: 1, 
                        get_query: () => ({
                            filters: { name: ['like', '%repair%'] }
                        })
                    },
                    { 
                        label: 'Spare Part', 
                        fieldname: 'spare_part', 
                        fieldtype: 'Link', 
                        options: 'Item', 
                        in_list_view: 1, 
                        read_only: true, 
                        reqd: 1 
                    },
                    { 
                        label: 'Repair Responsible Party', 
                        fieldname: 'repair_responsible_party', 
                        fieldtype: 'Link', 
                        options: 'Supplier', 
                        in_list_view: 1,
                        reqd: 1 
                    },
                    { 
                        label: 'Serial No.', 
                        fieldname: 'serial_no', 
                        fieldtype: 'Data', 
                        in_list_view: 1, 
                        reqd: 1, 
                        read_only: true 
                    },
                    { 
                        label: 'Line Id', 
                        fieldname: 'line_id', 
                        fieldtype: 'Link', 
                        options: 'Workstation Spare Parts', 
                        in_list_view: 1,
                        read_only: true 
                    },
                    { 
                        label: 'Asset', 
                        fieldname: 'asset', 
                        fieldtype: 'Link', 
                        options: 'Asset', 
                        in_list_view: 1,
                        read_only: true
                    },
                ]
            },
        ],
        primary_action_label: 'Create Service Request & Move History',
        primary_action: async (values) => {
            await process_service_request_creation(values, d, listview, last_window_asset_repair);
        }
    });


    // Setup field syncing
    const field_mappings = [
        { parent: 'default_target_warehouse', child: 'target_warehouse' },
        { parent: 'default_repair_responsible_party', child: 'repair_responsible_party' }
    ];

    add_sync_field_to_child_table(
        d,
        { fieldname: 'default_target_warehouse', label: 'Default Target Warehouse', fieldtype: 'Link' },
        'spares_details_for_stock_entry',
        field_mappings
    );

    add_sync_field_to_child_table(
        d,
        { fieldname: 'default_repair_responsible_party', label: 'Default Repair Responsible Party', fieldtype: 'Link' },
        'spares_details_for_stock_entry',
        field_mappings
    );

    if (all_selected_docs.length > 0) {
        d.show();
    }

}).hide();
        // let send_for_repair_btn = listview.page.add_action_item(__("Send For Repair: Issue SR"), async () => {
        //     if (!repair_warehouse_name){
        //         frappe.throw({
        //                     title: "Repair Warehouse Missing",
        //                     message: `
        //                         <b>Default Repair Warehouse is not configured!</b><br><br>
        //                         Please set the <b>Default Repair Warehouse</b> in the 
        //                         <b>Workstation Spares Settings</b> before performing this action.<br>
        //                         👉 <a href="/app/workstation-spares-settings/Workstation%20Spares%20Settings" 
        //                     target="_blank" 
        //                     style="font-weight:600; color:#2980b9;">
        //                         Open Workstation Spares Settings
        //                     </a>
        //                     `
        //                 });
        //             return;
        //     }

        //     let selected_rows_names = listview.get_checked_items();
        //     let all_selected_docs = []
        //     let selected_rows_names_list = []
        //     for (const selected_row of selected_rows_names) {
        //         selected_rows_names_list.push(selected_row.name)
        //     }
        //     // console.log('===== here is the selected_rows_names_list  = ', selected_rows_names_list)
        //     await check_spare_history_and_stock_entry(selected_rows_names_list,all_selected_docs)
        //     const spare_table_data = all_selected_docs.map(row_doc => {
        //         return {
        //             source_warehouse: row_doc.source_warehouse,
        //             target_warehouse: repair_warehouse_name,
        //             spare_part: row_doc.spare_part,
        //             // repair_start_date: today_date,
        //             line_id: row_doc.name ,
        //             serial_no: row_doc.item_serial_number,
        //             asset:row_doc.asset_reference,
        //             // maintenance_responsible_party :
        //         };
        //     })
        //     let d = new frappe.ui.Dialog({
        //         title: 'Enter Spare Details: Send For Repair',
        //         size: 'extra-large',
        //         fields: [
        //             // Parent sync fields
        //             {
        //                 label: 'Default Repair Start Date',
        //                 fieldname: 'default_repair_start_date',
        //                 fieldtype: 'Date',
        //                 reqd: 1, 
        //                 description: 'This date will be applied to all rows below',
        //                 default:today_date
        //             },
        //             {
        //                 label: 'Default Target Warehouse',
        //                 fieldname: 'default_target_warehouse',
        //                 fieldtype: 'Link',
        //                 options: 'Warehouse',
        //                 description: 'This warehouse will be applied to all rows below',
        //                 default:repair_warehouse_name,
        //                 get_query: () => {
        //                     return {
        //                         filters: {
        //                             name: ['like', '%repair%']
        //                         }
        //                     };
        //                 }
        //             },
        //             {
        //                 label: 'Default Repair Responsible Party',
        //                 fieldname: 'default_repair_responsible_party',
        //                 fieldtype: 'Link',
        //                 options: 'Supplier',
        //                 description: 'This party will be applied to all rows below'
        //             },
        //             {
        //                 fieldname: 'column_break_1',
        //                 fieldtype: 'Column Break'
        //             },
        //             {
        //                 fieldname: 'section_break_1',
        //                 fieldtype: 'Section Break',
        //                 label: 'Spares Details'
        //             },
        //             // Child table
        //             {
        //                 label: 'Spares Details For Stock Entry',
        //                 fieldname: 'spares_details_for_stock_entry',
        //                 fieldtype: 'Table',
        //                 cannot_add_rows: true,
        //                 in_place_edit: true,
        //                 data: spare_table_data,
        //                 reqd:1,
        //                 fields: [
        //                     { 
        //                         label: 'Source Warehouse', 
        //                         fieldname: 'source_warehouse', 
        //                         fieldtype: 'Link', 
        //                         options: 'Warehouse', 
        //                         in_list_view: 1, 
        //                         width: 150, 
        //                         reqd: 1, 
        //                         read_only: true 
        //                     },
        //                     {
        //                         label: 'Target Warehouse', 
        //                         fieldname: 'target_warehouse', 
        //                         fieldtype: 'Link', 
        //                         options: 'Warehouse', 
        //                         in_list_view: 1, 
        //                         reqd: 1, 
        //                         get_query: () => {
        //                             return {
        //                                 filters: {
        //                                     name: ['like', '%repair%']
        //                                 }
        //                             };
        //                         }
        //                     },
        //                     { 
        //                         label: 'Spare Part', 
        //                         fieldname: 'spare_part', 
        //                         fieldtype: 'Link', 
        //                         options: 'Item', 
        //                         in_list_view: 1, 
        //                         read_only: true, 
        //                         reqd: 1 
        //                     },
        //                     { 
        //                         label: 'Repair Responsible Party', 
        //                         fieldname: 'repair_responsible_party', 
        //                         fieldtype: 'Link', 
        //                         options: 'Supplier', 
        //                         in_list_view: 1,
        //                         reqd: 1 
        //                     },
        //                     { 
        //                         label: 'Serial No.', 
        //                         fieldname: 'serial_no', 
        //                         fieldtype: 'Data', 
        //                         in_list_view: 1, 
        //                         reqd: 1, 
        //                         read_only: true 
        //                     },
        //                     { 
        //                         label: 'Line Id', 
        //                         fieldname: 'line_id', 
        //                         fieldtype: 'Link', 
        //                         options: 'Workstation Spare Parts', 
        //                         in_list_view: 1 ,
        //                         read_only: true 
        //                     },
        //                     { 
        //                         label: 'Asset', 
        //                         fieldname: 'asset', 
        //                         fieldtype: 'Link', 
        //                         options: 'Asset', 
        //                         in_list_view: 1,
        //                         read_only: true
        //                     },
        //                 ]
        //             },
        //         ],
        //         primary_action_label: 'Create Service Request & Stock Entry',
        //         primary_action: async (values) => {
        //             await validate_required_table_fields(
        //                 d,                               
        //                 "spares_details_for_stock_entry",
        //                 values.spares_details_for_stock_entry 
        //             );

        //             let entry_date = values.default_repair_start_date;
        //             let every_line_po = {};
        //             let suppliers = {};
        //             let service_request_name = null;
        //             values.spares_details_for_stock_entry.forEach(row => {
        //                 const sup = row.repair_responsible_party;
        //                 // const asset = row.asset;
        //                 // const spare_parts_reference = row.line_id;
        //                 if (!suppliers[sup]) suppliers[sup] = [];
        //                 suppliers[sup].push(row);
        //             });

        //             const payload = [];
        //             for (const sup in suppliers) {
        //                 payload.push({
        //                     supplier: sup,
        //                     schedule_date: entry_date,
        //                     asset_repair_reference: last_window_asset_repair || "",
        //                     rows: suppliers[sup]
        //                 });
        //             }

        //             try {
        //                 freeze_ui('Creating Service Requests...');  
                        
        //                 for (const p of payload) {
        //                     await frappe.call({
        //                         method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_service_request_for_supplier",
        //                         args: { data: p },
        //                         callback: function (r) {
        //                             if (r.message) {
        //                                 p.rows.forEach(row => {
        //                                     every_line_po[row.line_id] = r.message.sr_name;
        //                                     service_request_name = r.message.sr_name;
        //                                 });
        //                             }
        //                         }
        //                     });
        //                 }
                        
        //                 unfreeze_ui();
        //                 frappe.msgprint(__("Service Request created successfully"));
        //             } catch (err) {
        //                 unfreeze_ui();
        //                 console.error(err);
        //                 frappe.throw(__("Failed to create Service Request(s)"));
        //                 return;
        //             }
        //             run();


        //             // let spare_part = frm.doc.spare_part;
        //             // let to_warehouse = frm.doc.spare_status === "In Use" ?  frm.doc.target_warehouse : "";
        //             // let from_warehouse = frm.doc.spare_status === "In Use" ? frm.doc.source_warehouse  : "";
        //             // let install_date = frm.doc.date_of_installation;

        //             // let stk_entry_type = "Material Transfer";

        //             // frappe.set_route("Form", "Stock Entry", "new-stock-entry-1");

        //             // setTimeout(async () => {
        //             //     if (cur_frm && cur_frm.doc.doctype === "Stock Entry") {
        //             //         cur_frm.set_value("stock_entry_type", stk_entry_type);
        //             //         cur_frm.set_value("custom_stock_entry_reference", listview.doctype);
        //             //         cur_frm.set_value("set_posting_time", 1);
        //             //         cur_frm.clear_table("items");
        //             //         cur_frm.set_value("posting_date" , entry_date);
        //             //         cur_frm.set_value("remarks", last_window_asset_repair || "");
        //             //         cur_frm.set_value("set_posting_time", 0);

        //             //         (async () => {
        //             //             for (const row of values.spares_details_for_stock_entry) {
                                    
        //             //                 // Get item UOM
        //             //                 const r = await frappe.db.get_value('Item', row.spare_part, 'stock_uom');
        //             //                 if (!r.message) {
        //             //                     frappe.msgprint("Item UOM not found");
        //             //                     continue;
        //             //                 }
        //             //                 let item_uom = r.message.stock_uom;
        //             //                 let child = cur_frm.add_child("items", {
        //             //                     s_warehouse: row.source_warehouse,
        //             //                     t_warehouse: row.target_warehouse,
        //             //                     item_code: row.spare_part,
        //             //                     qty: 1,
        //             //                     transfer_qty: 1,
        //             //                     uom: item_uom,
        //             //                     stock_uom: item_uom,
        //             //                     conversion_factor: 1,
        //             //                     use_serial_batch_fields: 1,
        //             //                     serial_no: row.serial_no,
        //             //                     custom_stock_item_move_reference: row.line_id
        //             //                 });
        //             //             }
        //             //             cur_frm.refresh_field("items");
        //             //             cur_frm.refresh();
        //             //             await cur_frm.save();
        //             //             run();
        //             //         })();
        //             //     }

        //             //     // console.log('here is the stock move history doc --',spare_move_his_doc)
        //             //     // console.log('move history doc name -- --',spare_move_his_doc.name)
        //             // }, 1200);

        //             //  =================== Spare Move History Log Creation =========================== //
        //             function run() {
        //                 setTimeout(() => {
        //                     values.spares_details_for_stock_entry.forEach(async row => {
        //                         spare_entry_doc = await frappe.db.get_doc("Workstation Spare Parts", row.line_id)
        //                         console.log('herei is the dpare entry doc = ', spare_entry_doc)
        //                         console.log('herei is service_request_name = ', service_request_name)

        //                         frappe.db.get_value('Item', row.spare_part, 'stock_uom').then(r => {
        //                             if (!r.message) {
        //                                 frappe.msgprint("Item UOM not found");
        //                                 return;
        //                             }
        //                             // console.log('herei is the dpare entry doc = ', spare_entry_doc)
        //                             let move_history_data = {
        //                                 spare_entry_reference: row.line_id,
        //                                 workstation: spare_entry_doc.workstation,
        //                                 spare_part: row.spare_part,
        //                                 from_warehouse: row.source_warehouse,
        //                                 to_warehouse: row.target_warehouse,
        //                                 entry_date: entry_date,
        //                                 old_status: spare_entry_doc.spare_status,
        //                                 current_status: "Sent For Repair",
        //                                 // repair_po_reference: every_line_po[row.line_id] ,
        //                                 stock_entry_reference: "" , //cur_frm.doc.name
        //                                 asset_repair_reference: last_window_asset_repair,
        //                                 asset_reference: row.asset,
        //                                 service_request_reference: service_request_name,
        //                                 entry_details: `Spare item (${row.spare_part}) was sent for repair.
        //                                 Source Warehouse: ${row.source_warehouse}
        //                                 Target Warehouse (Repair Store): ${row.target_warehouse}
        //                                 Repair Start Date: ${entry_date}
        //                                 Workstation: ${spare_entry_doc.workstation}
        //                                 Reference Line ID: ${row.line_id}
        //                                 Serial No: ${row.serial_no || "N/A"}
        //                                 Stock Entry Reference: ${cur_frm.doc.name}
        //                                 Note: Item has been moved out of the workstation and transferred to the repair store for maintenance work.`
        //                             };
        //                             frappe.call({
        //                                 method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
        //                                 args: {
        //                                     data: move_history_data
        //                                 },
        //                                 callback: function (r) {
        //                                     if (r.message) {
        //                                         // spare_entry_doc.spare_status = move_history_data.current_status
        //                                         // spare_entry_doc.save();
        //                                         // spare_entry_doc.db.commit();
        //                                         // frappe.call({
        //                                         //     method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.update_spare_status",
        //                                         //     args: {
        //                                         //         docname: row.line_id,
        //                                         //         //new_status: "Sent For Repair"
        //                                         //     }
        //                                         // });
        //                                         frappe.msgprint(__("Spare Move History Log created: ") + r.message);
        //                                     } else {
        //                                         frappe.msgprint(__("Spare Move History Log creation failed or returned no id."));
        //                                     }
        //                                 }
        //                             })

        //                         })
        //                     })
        //                 }, 700);
        //             }
                    
        //             d.hide();
        //         }
        //     });

        //     // Setup sync for fields
        //         const field_mappings = [
        //             { parent: 'default_target_warehouse', child: 'target_warehouse' },
        //             { parent: 'default_repair_responsible_party', child: 'repair_responsible_party' }
        //         ];

        //         // Apply sync for warehouse
        //         add_sync_field_to_child_table(
        //             d,
        //             { fieldname: 'default_target_warehouse', label: 'Default Target Warehouse', fieldtype: 'Link' },
        //             'spares_details_for_stock_entry',
        //             field_mappings
        //         );

        //         // Apply sync for party
        //         add_sync_field_to_child_table(
        //             d,
        //             { fieldname: 'default_repair_responsible_party', label: 'Default Repair Responsible Party', fieldtype: 'Link' },
        //             'spares_details_for_stock_entry',
        //             field_mappings
        //         );

        //     if (all_selected_docs.length>0){
        //         d.show();
        //     }

        // }).hide();

        let recieve_in_warehouse_btn = listview.page.add_action_item(__("Receive From Repair: In Warehouse"), async () => {
            if (!repairable_storage_warehouse_name){
                settings_not_found_validation_check("Storage Warehouse For Repairables")
            }
            let selected_rows_names = listview.get_checked_items();
            let all_selected_docs = []
            let selected_rows_names_list = []
            for (const selected_row of selected_rows_names) {
                selected_rows_names_list.push(selected_row.name)
            }
            // console.log('===== here is the selected_rows_names_list  = ', selected_rows_names_list)
            await check_spare_history_and_stock_entry(selected_rows_names_list,all_selected_docs)
            
            const spare_table_data = all_selected_docs.map(row_doc => {
                return {
                    source_warehouse: row_doc.source_warehouse,
                    target_warehouse: repairable_storage_warehouse_name,
                    spare_part: row_doc.spare_part,
                    received_date: today_date,
                    line_id: row_doc.name ,
                    serial_no: row_doc.item_serial_number,
                    asset:row_doc.asset_reference
                };
            })
            let d = new frappe.ui.Dialog({
                title: 'Enter Detials: Receive From Repair: In Warehouse',
                size: 'extra-large',
                fields: [
                    { label: 'Received Date', fieldname: 'received_date', fieldtype: 'Date',default:today_date, in_list_view: 1, "reqd": 1 },
                    {
                        label: 'Default Target Warehouse',
                        fieldname: 'default_target_warehouse',
                        fieldtype: 'Link',
                        options: 'Warehouse',
                        description: 'This warehouse will be applied to all rows below',
                        default:repairable_storage_warehouse_name,
                    },
                            {
                                fieldname: 'column_break_1',
                                fieldtype: 'Column Break'
                            },
                            {
                                fieldname: 'section_break_1',
                                fieldtype: 'Section Break',
                                label: 'Spares Details'
                            },
                    {
                        label: 'Spares Details For Stock Entry',
                        fieldname: 'spares_details_for_stock_entry',
                        fieldtype: 'Table',
                        cannot_add_rows: true,
                        in_place_edit: false,
                        data: spare_table_data,
                        fields: [
                            
                            
                            { label: 'Source Warehouse', fieldname: 'source_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, width: 150, "reqd": 1, read_only: true },
                            {
                                label: 'Target Warehouse', fieldname: 'target_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, "reqd": 1, get_query: () => {
                                    // return {
                                    //     filters: {
                                    //         // name: ['like', '%repair%'],
                                    //         custom_is_spares_warehouse: false
                                    //     }
                                    // }
                                }
                            },
                            { label: 'Spare Part', fieldname: 'spare_part', fieldtype: 'Link', options: 'Item', in_list_view: 1, read_only: true, "reqd": 1 },
                            // { label: 'Repair Responsible Party', fieldname: 'repair_responsible_party', fieldtype: 'Link',options:'Supplier', in_list_view: 1 },
                            { label: 'Serial No.', fieldname: 'serial_no', fieldtype: 'Data', in_list_view: 1, width: '10%', "reqd": 1, read_only: true },
                            { 
                                label: 'Line Id', 
                                fieldname: 'line_id', 
                                fieldtype: 'Link', 
                                options: 'Workstation Spare Parts', 
                                in_list_view: 1 ,
                                read_only: true 
                            },
                            { 
                                label: 'Asset', 
                                fieldname: 'asset', 
                                fieldtype: 'Link', 
                                options: 'Asset', 
                                in_list_view: 0,
                                read_only: true
                            },
                        ]
                    },
                ],
                primary_action_label: 'Create Stock Entry',
                primary_action: async (values) => {
                    await validate_required_table_fields(
                        d,                               
                        "spares_details_for_stock_entry",
                        values.spares_details_for_stock_entry 
                    );
                    let received_date = values.received_date;
                    let stk_entry_type = "Material Transfer";
                    frappe.set_route("Form", "Stock Entry", "new-stock-entry-1");
                    setTimeout(async () => {
                        if (cur_frm && cur_frm.doc.doctype === "Stock Entry") {
                            cur_frm.set_value("stock_entry_type", stk_entry_type);
                            cur_frm.set_value("custom_stock_entry_reference", listview.doctype);
                            // cur_frm.set_value("to_warehouse", to_warehouse);
                            // cur_frm.set_value("from_warehouse", from_warehouse);
                            cur_frm.set_value("set_posting_time", 1);
                            cur_frm.set_value("posting_date", received_date);
                            // cur_frm.set_value("custom_stock_item_move_reference",frm.doc.name );
                            cur_frm.clear_table("items");
                            (async () => {
                                for (const row of values.spares_details_for_stock_entry){                                    // cur_frm.set_value("posting_date", received_date);
                                    // Get item UOM
                                    const r = await frappe.db.get_value('Item', row.spare_part, 'stock_uom');
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        continue;
                                    }
                                    let item_uom = r.message.stock_uom;
                                    let child = cur_frm.add_child("items", {
                                        s_warehouse: row.source_warehouse,
                                        t_warehouse: row.target_warehouse,
                                        item_code: row.spare_part,
                                        qty: 1,
                                        transfer_qty: 1,
                                        uom: item_uom,
                                        stock_uom: item_uom,
                                        conversion_factor: 1,
                                        use_serial_batch_fields: 1,
                                        serial_no: row.serial_no,
                                        custom_stock_item_move_reference: row.line_id
                                    });
                                }
                                cur_frm.refresh_field("items");
                                cur_frm.refresh();
                                await cur_frm.save();
                                run();
                            })();
                        }
                    }, 1200);
                    //  =================== Spare Move History Log Creation =========================== //
                    function run() {
                        setTimeout(() => {
                            values.spares_details_for_stock_entry.forEach(async row => {
                                spare_entry_doc = await frappe.db.get_doc("Workstation Spare Parts", row.line_id)
                                // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                frappe.db.get_value('Item', row.spare_part, 'stock_uom').then(r => {
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        return;
                                    }
                                    // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                    let move_history_data = {
                                        spare_entry_reference: row.line_id,
                                        workstation: spare_entry_doc.workstation,
                                        spare_part: row.spare_part,
                                        from_warehouse: row.source_warehouse,
                                        to_warehouse: row.target_warehouse,
                                        entry_date: received_date,
                                        old_status: spare_entry_doc.spare_status,
                                        current_status: "Available",
                                        // repair_po_reference: every_line_po[row.line_id] ,
                                        stock_entry_reference: cur_frm.doc.name,
                                        asset_repair_reference: last_window_asset_repair,
                                        asset_reference: row.asset,
                                        entry_details: `Spare item (${row.spare_part}) was sent for repair.
                                        Source Warehouse: ${row.source_warehouse}
                                        Target Warehouse (Repair Store): ${row.target_warehouse}
                                        Repair Start Date: ${received_date}
                                        Workstation: ${spare_entry_doc.workstation}
                                        Reference Line ID: ${row.line_id}
                                        Serial No: ${row.serial_no || "N/A"}
                                        Stock Entry Reference: ${cur_frm.doc.name}
                                        Note: Item has been moved out of the workstation and transferred to the repair store for maintenance work.`
                                    };
                                    frappe.call({
                                        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
                                        args: {
                                            data: move_history_data
                                        },
                                        callback: function (r) {
                                            if (r.message) {
                                                // frappe.call({
                                                //     method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.update_spare_status",
                                                //     args: {
                                                //         docname: row.line_id,
                                                //         //new_status: "Available"
                                                //     }
                                                // });
                                                frappe.msgprint(__("Spare Move History Log created: ") + r.message);
                                            } else {
                                                frappe.msgprint(__("Spare Move History Log creation failed or returned no id."));
                                            }
                                        }
                                    })

                                })
                            })
                        }, 1000);

                        d.hide();
                    }
                }
            });
            // Setup sync for fields
                const field_mappings = [
                    { parent: 'default_target_warehouse', child: 'target_warehouse' },
                ];
                // Apply sync for warehouse
                add_sync_field_to_child_table(
                    d,
                    { fieldname: 'default_target_warehouse', label: 'Default Target Warehouse', fieldtype: 'Link' },
                    'spares_details_for_stock_entry',
                    field_mappings
                );
            if (all_selected_docs.length>0){
                d.show();
            }

        }).hide();





        //  Receive From Repair : Re-install on Same Machine

        let reinstall_on_machine_btn = listview.page.add_action_item(__("Receive From Repair: Re-install on Same Machine"), async () => {
            let selected_rows_names = listview.get_checked_items();
            let all_selected_docs = []
            let selected_rows_names_list = []
            for (const selected_row of selected_rows_names) {
                selected_rows_names_list.push(selected_row.name)
            }
            // console.log('===== here is the selected_rows_names_list  = ', selected_rows_names_list)
            await check_spare_history_and_stock_entry(selected_rows_names_list,all_selected_docs)
            
            const spare_table_data = all_selected_docs.map(row_doc => {
                return {
                    source_warehouse: row_doc.source_warehouse,
                    target_warehouse: row_doc.target_warehouse,
                    spare_part: row_doc.spare_part,
                    received_date: today_date,
                    line_id: row_doc.name ,
                    serial_no: row_doc.item_serial_number,
                    asset:row_doc.asset_reference
                    // maintenance_responsible_party :
                };
            })
            let d = new frappe.ui.Dialog({
                title: 'Enter Detials: Receive From Repair: Re-install on Same Machine',
                size: 'extra-large',
                fields: [
                    { label: 'Received Date', fieldname: 'received_date', fieldtype: 'Date',default:today_date, in_list_view: 1, "reqd": 1 },
                    {
                        fieldname: 'column_break_1',
                        fieldtype: 'Column Break'
                    },
                    {
                        fieldname: 'section_break_1',
                        fieldtype: 'Section Break',
                        label: 'Spares Details'
                    },
                    {
                        label: 'Spares Details For Stock Entry',
                        fieldname: 'spares_details_for_stock_entry',
                        fieldtype: 'Table',
                        cannot_add_rows: true,
                        in_place_edit: false,
                        data: spare_table_data,
                        fields: [
                            { label: 'Source Warehouse', fieldname: 'source_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, width: 150, "reqd": 1, read_only: true },
                            {
                            label: 'Target Warehouse', fieldname: 'target_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, "reqd": 1,read_only:true},
                            { label: 'Spare Part', fieldname: 'spare_part', fieldtype: 'Link', options: 'Item', in_list_view: 1, read_only: true, "reqd": 1 },
                            // { label: 'Repair Responsible Party', fieldname: 'repair_responsible_party', fieldtype: 'Link',options:'Supplier', in_list_view: 1 },
                            { label: 'Serial No.', fieldname: 'serial_no', fieldtype: 'Data', in_list_view: 1, width: '10%', "reqd": 1, read_only: true },
                            { 
                                label: 'Line Id', 
                                fieldname: 'line_id', 
                                fieldtype: 'Link', 
                                options: 'Workstation Spare Parts', 
                                in_list_view: 1 ,
                                read_only: true 
                            },
                            { 
                                label: 'Asset', 
                                fieldname: 'asset', 
                                fieldtype: 'Link', 
                                options: 'Asset', 
                                in_list_view: 0,
                                read_only: true
                            },
                        ]
                    },
                ],
                primary_action_label: 'Create Stock Entry',
                primary_action: async (values) => {
                    await validate_required_table_fields(
                        d,                               
                        "spares_details_for_stock_entry",
                        values.spares_details_for_stock_entry 
                    );
                    let received_date = values.received_date
                    let stk_entry_type = "Material Transfer";
                    frappe.set_route("Form", "Stock Entry", "new-stock-entry-1");
                    setTimeout(async() => {
                        if (cur_frm && cur_frm.doc.doctype === "Stock Entry") {
                            cur_frm.set_value("stock_entry_type", stk_entry_type);
                            cur_frm.set_value("custom_stock_entry_reference", listview.doctype);
                            // cur_frm.set_value("to_warehouse", to_warehouse);
                            // cur_frm.set_value("from_warehouse", from_warehouse);
                            cur_frm.set_value("set_posting_time", 1);
                            // cur_frm.set_value("custom_stock_item_move_reference",frm.doc.name );
                            cur_frm.clear_table("items");
                            cur_frm.set_value("posting_date", received_date);

                            (async () => {
                                for (const row of values.spares_details_for_stock_entry){                                    // Get item UOM
                                    const r = await frappe.db.get_value('Item', row.spare_part, 'stock_uom');
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        continue;
                                    }
                                    let item_uom = r.message.stock_uom;
                                    let child = cur_frm.add_child("items", {
                                        s_warehouse: row.source_warehouse,
                                        t_warehouse: row.target_warehouse,
                                        item_code: row.spare_part,
                                        qty: 1,
                                        transfer_qty: 1,
                                        uom: item_uom,
                                        stock_uom: item_uom,
                                        conversion_factor: 1,
                                        use_serial_batch_fields: 1,
                                        serial_no: row.serial_no,
                                        custom_stock_item_move_reference: row.line_id
                                    });
                                }
                                cur_frm.refresh_field("items");
                                cur_frm.refresh();
                                await cur_frm.save();
                                run();
                            })();
                        }
                    }, 600);
                    //  =================== Spare Move History Log Creation =========================== //
                    // 
                    function run() {
                        setTimeout(() => {
                            values.spares_details_for_stock_entry.forEach(async row => {
                                spare_entry_doc = await frappe.db.get_doc("Workstation Spare Parts", row.line_id)
                                // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                frappe.db.get_value('Item', row.spare_part, 'stock_uom').then(r => {
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        return;
                                    }
                                    // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                    let move_history_data = {
                                        spare_entry_reference: row.line_id,
                                        workstation: spare_entry_doc.workstation,
                                        spare_part: row.spare_part,
                                        from_warehouse: row.source_warehouse,
                                        to_warehouse: row.target_warehouse,
                                        entry_date: received_date,
                                        old_status: spare_entry_doc.spare_status,
                                        current_status: "In Use",
                                        // repair_po_reference: every_line_po[row.line_id] ,
                                        stock_entry_reference: cur_frm.doc.name,
                                        asset_repair_reference: last_window_asset_repair,
                                        asset_reference: row.asset,
                                        entry_details: `Spare item (${row.spare_part}) was sent for repair.
                                        Source Warehouse: ${row.source_warehouse}
                                        Target Warehouse (Repair Store): ${row.target_warehouse}
                                        Repair Start Date: ${received_date}
                                        Workstation: ${spare_entry_doc.workstation}
                                        Reference Line ID: ${row.line_id}
                                        Serial No: ${row.serial_no || "N/A"}
                                        Stock Entry Reference: ${cur_frm.doc.name}
                                        Note: Item has been moved out of the workstation and transferred to the repair store for maintenance work.`
                                    };
                                    frappe.call({
                                        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
                                        args: {
                                            data: move_history_data
                                        },
                                        callback: function (r) {
                                            if (r.message) {
                                                // frappe.call({
                                                //     method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.update_spare_status",
                                                //     args: {
                                                //         docname: row.line_id,
                                                //         //new_status: "In Use"
                                                //     }
                                                // });
                                                frappe.msgprint(__("Spare Move History Log created: ") + r.message);
                                            } else {
                                                frappe.msgprint(__("Spare Move History Log creation failed or returned no id."));
                                            }
                                        }
                                    })

                                })
                            })
                        }, 1000);
                    }
                    d.hide();
                }
            });
            if (all_selected_docs.length>0){
                d.show();
            }

        }).hide();







        // ================================== Scrap/Consume entry  ===================================== 

        let scrap_btn = listview.page.add_action_item(__("Scrap/Consume Spare"), async () => {
            let selected_rows_names = listview.get_checked_items();
            let all_selected_docs = []
            let selected_rows_names_list = []
            for (const selected_row of selected_rows_names) {
                selected_rows_names_list.push(selected_row.name)
            }
            // console.log('===== here is the selected_rows_names_list  = ', selected_rows_names_list)
            await check_spare_history_and_stock_entry(selected_rows_names_list,all_selected_docs)
            
            const spare_table_data = all_selected_docs.map(row_doc => {
                return {
                    source_warehouse: row_doc.source_warehouse,
                    // target_warehouse: "",
                    spare_part: row_doc.spare_part,
                    entry_date: today_date,
                    line_id: row_doc.name ,
                    serial_no: row_doc.item_serial_number,
                    asset:row_doc.asset_reference
                    // maintenance_responsible_party :
                };
            })
            let d = new frappe.ui.Dialog({
                title: 'Enter Detials: Scrap/Consume Spare',
                size: 'extra-large',
                fields: [
                    { label: 'Entry Date', fieldname: 'entry_date', fieldtype: 'Date',default:today_date, in_list_view: 1, "reqd": 1 },
                            {
                                fieldname: 'column_break_1',
                                fieldtype: 'Column Break'
                            },
                            {
                                fieldname: 'section_break_1',
                                fieldtype: 'Section Break',
                                label: 'Spares Details'
                            },
                    {
                        label: 'Spares Details For Stock Entry',
                        fieldname: 'spares_details_for_stock_entry',
                        fieldtype: 'Table',
                        cannot_add_rows: true,
                        in_place_edit: false,
                        data: spare_table_data,
                        fields: [
                            { label: 'Source Warehouse', fieldname: 'source_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, width: 150, "reqd": 1, read_only: true },
                            // { label: 'Target Warehouse', fieldname: 'target_warehouse', fieldtype: 'Link',options:'Warehouse', in_list_view: 1,"reqd": 1, get_query: () => {
                            //                                                                                     return {
                            //                                                                                         filters: {
                            //                                                                                             // name: ['like', '%repair%'],
                            //                                                                                             custom_is_spares_warehouse:false
                            //                                                                                         }
                            //                                                                                     }
                            //                                                                                 } },
                            { label: 'Spare Part', fieldname: 'spare_part', fieldtype: 'Link', options: 'Item', in_list_view: 1, read_only: true, "reqd": 1 },
                            // { label: 'Repair Responsible Party', fieldname: 'repair_responsible_party', fieldtype: 'Link',options:'Supplier', in_list_view: 1 },
                            { label: 'Serial No.', fieldname: 'serial_no', fieldtype: 'Data', in_list_view: 1, width: '10%', "reqd": 1, read_only: true },
                            { 
                                label: 'Line Id', 
                                fieldname: 'line_id', 
                                fieldtype: 'Link', 
                                options: 'Workstation Spare Parts', 
                                in_list_view: 1 ,
                                read_only: true 
                            },
                            { 
                                label: 'Asset', 
                                fieldname: 'asset', 
                                fieldtype: 'Link', 
                                options: 'Asset', 
                                in_list_view: 0,
                                read_only: true
                            },
                        ]
                    },
                ],
                primary_action_label: 'Create Stock Entry',
                primary_action: async (values) => {
                    await validate_required_table_fields(
                        d,                               
                        "spares_details_for_stock_entry",
                        values.spares_details_for_stock_entry 
                    );
                    let entry_date = values.entry_date;
                    let stk_entry_type = await new Promise((resolve) => {
                            frappe.call({
                                method: "frappe.client.get_list",
                                args: {
                                    doctype: "Stock Entry Type",
                                    filters: { name: "Spares Permanent Consumption" },
                                    limit_page_length: 1
                                },
                                callback: function(r) {
                                    if (!r.message || !r.message.length) {
                                        frappe.call({
                                            method: "frappe.client.insert",
                                            args: {
                                                doc: {
                                                    doctype: "Stock Entry Type",
                                                    name: "Spares Permanent Consumption",
                                                    purpose: "Material Issue",
                                                    disabled: 0
                                                }
                                            },
                                            callback: function() {
                                                resolve("Spares Permanent Consumption");
                                            }
                                        });
                                    } else {
                                        resolve("Spares Permanent Consumption");
                                    }
                                }
                            });
                        });

                    frappe.set_route("Form", "Stock Entry", "new-stock-entry-1");
                    setTimeout(async() => {
                        if (cur_frm && cur_frm.doc.doctype === "Stock Entry") {
                            cur_frm.set_value("stock_entry_type", stk_entry_type);
                            cur_frm.set_value("custom_stock_entry_reference", listview.doctype);
                            // cur_frm.set_value("to_warehouse", to_warehouse);
                            // cur_frm.set_value("from_warehouse", from_warehouse);
                            cur_frm.set_value("set_posting_time", 1);
                            cur_frm.set_value("posting_date" , entry_date);
                            cur_frm.set_value("remarks", last_window_asset_repair || "");
                            // cur_frm.set_value("custom_stock_item_move_reference",frm.doc.name );
                            cur_frm.clear_table("items");

                            (async () => {
                                for (const row of values.spares_details_for_stock_entry){                                    // cur_frm.set_value("posting_date", row.entry_date);
                                    // Get item UOM
                                    const r = await frappe.db.get_value('Item', row.spare_part, 'stock_uom');
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        continue;
                                    }
                                    let item_uom = r.message.stock_uom;
                                    let child = cur_frm.add_child("items", {
                                        s_warehouse: row.source_warehouse,
                                        t_warehouse: row.target_warehouse,
                                        item_code: row.spare_part,
                                        qty: 1,
                                        transfer_qty: 1,
                                        uom: item_uom,
                                        stock_uom: item_uom,
                                        conversion_factor: 1,
                                        use_serial_batch_fields: 1,
                                        serial_no: row.serial_no,
                                        custom_stock_item_move_reference: row.line_id
                                    });
                                }
                                cur_frm.refresh_field("items");
                                cur_frm.refresh();
                                await cur_frm.save();
                                run();
                            })();
                        }
                    }, 600);
                    //  =================== Spare Move History Log Creation =========================== //
                    // 
                    function run() {
                        setTimeout(() => {
                            values.spares_details_for_stock_entry.forEach(async row => {
                                spare_entry_doc = await frappe.db.get_doc("Workstation Spare Parts", row.line_id)
                                // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                frappe.db.get_value('Item', row.spare_part, 'stock_uom').then(r => {
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        return;
                                    }
                                    // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                    let move_history_data = {
                                        spare_entry_reference: row.line_id,
                                        workstation: spare_entry_doc.workstation,
                                        spare_part: row.spare_part,
                                        from_warehouse: row.source_warehouse,
                                        to_warehouse: row.target_warehouse,
                                        entry_date: entry_date,
                                        old_status: spare_entry_doc.spare_status,
                                        current_status: "Scrapped",
                                        // repair_po_reference: every_line_po[row.line_id] ,
                                        stock_entry_reference: cur_frm.doc.name,
                                        asset_repair_reference: last_window_asset_repair,
                                        asset_reference: row.asset,
                                        entry_details: `Spare item (${row.spare_part}) was sent for repair.
                                        Source Warehouse: ${row.source_warehouse}
                                        Target Warehouse: ${row.target_warehouse}
                                        Repair Start Date: ${entry_date}
                                        Workstation: ${spare_entry_doc.workstation}
                                        Reference Line ID: ${row.line_id}
                                        Serial No: ${row.serial_no || "N/A"}
                                        Stock Entry Reference: ${cur_frm.doc.name}
                                        Note: Item has been moved out of the workstation and transferred to the repair store for maintenance work.`
                                    };
                                    frappe.call({
                                        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
                                        args: {
                                            data: move_history_data
                                        },
                                        callback: function (r) {
                                            if (r.message) {
                                                // frappe.call({
                                                //     method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.update_spare_status",
                                                //     args: {
                                                //         docname: row.line_id,
                                                //         //new_status: "Consumed"
                                                //     }
                                                // });
                                                frappe.msgprint(__("Spare Move History Log created: ") + r.message);
                                            } else {
                                                frappe.msgprint(__("Spare Move History Log creation failed or returned no id."));
                                            }
                                        }
                                    })
                                })
                            })
                        }, 1000);
                    }
                    d.hide();
                }
            });
            if (all_selected_docs.length>0){
                d.show();
            }

        }).hide();





        // ================================== Remove From Machine: Make Available  ===================================== 

        let remove_from_machine_btn = listview.page.add_action_item(__("Remove From Machine: Make Available"), async () => {
            if (!repairable_storage_warehouse_name){
                settings_not_found_validation_check("Storage Warehouse For Repairables")
            }
            let selected_rows_names = listview.get_checked_items();
            let all_selected_docs = []
            let selected_rows_names_list = []
            for (const selected_row of selected_rows_names) {
                selected_rows_names_list.push(selected_row.name)
            }
            // console.log('===== here is the selected_rows_names_list  = ', selected_rows_names_list)
            await check_spare_history_and_stock_entry(selected_rows_names_list,all_selected_docs)
            
            const spare_table_data = all_selected_docs.map(row_doc => {
                return {
                    source_warehouse: row_doc.source_warehouse,
                    target_warehouse: repairable_storage_warehouse_name,
                    spare_part: row_doc.spare_part,
                    entry_date: today_date,
                    line_id: row_doc.name ,
                    serial_no: row_doc.item_serial_number,
                    asset:row_doc.asset_reference
                    // maintenance_responsible_party :
                };
            })
            let d = new frappe.ui.Dialog({
                title: 'Enter Detials: Remove From Machine: Make Available',
                size: 'extra-large',
                fields: [
                    { label: 'Entry Date', fieldname: 'entry_date', fieldtype: 'Date',default:today_date, in_list_view: 1, "reqd": 1 },
                    {
                        label: 'Default Target Warehouse',
                        fieldname: 'default_target_warehouse',
                        fieldtype: 'Link',
                        options: 'Warehouse',
                        description: 'This warehouse will be applied to all rows below',
                        default:repairable_storage_warehouse_name,
                    },
                    {
                        fieldname: 'column_break_1',
                        fieldtype: 'Column Break'
                    },
                    {
                        fieldname: 'section_break_1',
                        fieldtype: 'Section Break',
                        label: 'Spares Details'
                    },
                    {
                        label: 'Spares Details For Stock Entry',
                        fieldname: 'spares_details_for_stock_entry',
                        fieldtype: 'Table',
                        cannot_add_rows: true,
                        in_place_edit: false,
                        data: spare_table_data,
                        fields: [
                            { label: 'Source Warehouse', fieldname: 'source_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, width: 150, "reqd": 1, read_only: true },
                            {
                                label: 'Target Warehouse', fieldname: 'target_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, "reqd": 1, get_query: () => {
                                    return {
                                        filters: {
                                            // name: ['like', '%repair%'],
                                            custom_is_spares_warehouse: false
                                        }
                                    }
                                }
                            },
                            { label: 'Spare Part', fieldname: 'spare_part', fieldtype: 'Link', options: 'Item', in_list_view: 1, read_only: true, "reqd": 1 },
                            // { label: 'Repair Responsible Party', fieldname: 'repair_responsible_party', fieldtype: 'Link',options:'Supplier', in_list_view: 1 },
                            { label: 'Serial No.', fieldname: 'serial_no', fieldtype: 'Data', in_list_view: 1, width: '10%', "reqd": 1, read_only: true },
                            { 
                                label: 'Line Id', 
                                fieldname: 'line_id', 
                                fieldtype: 'Link', 
                                options: 'Workstation Spare Parts', 
                                in_list_view: 1 ,
                                read_only: true 
                            },
                            { 
                                label: 'Asset', 
                                fieldname: 'asset', 
                                fieldtype: 'Link', 
                                options: 'Asset', 
                                in_list_view: 0,
                                read_only: true
                            },
                        ]
                    },
                ],
                primary_action_label: 'Create Stock Entry',
                primary_action: async (values) => {
                    await validate_required_table_fields(
                        d,                               
                        "spares_details_for_stock_entry",
                        values.spares_details_for_stock_entry 
                    );
                    let entry_date = values.entry_date
                    let stk_entry_type = "Material Transfer";
                    frappe.set_route("Form", "Stock Entry", "new-stock-entry-1");
                    setTimeout(async() => {
                        if (cur_frm && cur_frm.doc.doctype === "Stock Entry") {
                            cur_frm.set_value("stock_entry_type", stk_entry_type);
                            cur_frm.set_value("custom_stock_entry_reference", listview.doctype);
                            // cur_frm.set_value("to_warehouse", to_warehouse);
                            // cur_frm.set_value("from_warehouse", from_warehouse);
                            cur_frm.set_value("set_posting_time", 1);
                            cur_frm.set_value("posting_date" , entry_date);
                            cur_frm.set_value("remarks", last_window_asset_repair || "");
                            // cur_frm.set_value("custom_stock_item_move_reference",frm.doc.name );
                            cur_frm.clear_table("items");

                            (async () => {
                                for (const row of values.spares_details_for_stock_entry){                                    // cur_frm.set_value("posting_date", row.entry_date);
                                    // Get item UOM
                                    const r = await frappe.db.get_value('Item', row.spare_part, 'stock_uom');
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        continue;
                                    }
                                    let item_uom = r.message.stock_uom;
                                    let child = cur_frm.add_child("items", {
                                        s_warehouse: row.source_warehouse,
                                        t_warehouse: row.target_warehouse,
                                        item_code: row.spare_part,
                                        qty: 1,
                                        transfer_qty: 1,
                                        uom: item_uom,
                                        stock_uom: item_uom,
                                        conversion_factor: 1,
                                        use_serial_batch_fields: 1,
                                        serial_no: row.serial_no,
                                        custom_stock_item_move_reference: row.line_id
                                    });
                                }
                                cur_frm.refresh_field("items");
                                cur_frm.refresh();
                                await cur_frm.save();
                                run();
                            })();
                        }
                    }, 600);
                    //  =================== Spare Move History Log Creation =========================== //
                    // 
                    function run() {
                        setTimeout(() => {
                            values.spares_details_for_stock_entry.forEach(async row => {
                                spare_entry_doc = await frappe.db.get_doc("Workstation Spare Parts", row.line_id)
                                // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                frappe.db.get_value('Item', row.spare_part, 'stock_uom').then(r => {
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        return;
                                    }
                                    // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                    let move_history_data = {
                                        spare_entry_reference: row.line_id,
                                        workstation: spare_entry_doc.workstation,
                                        spare_part: row.spare_part,
                                        from_warehouse: row.source_warehouse,
                                        to_warehouse: row.target_warehouse,
                                        entry_date: entry_date,
                                        old_status: spare_entry_doc.spare_status,
                                        current_status: "Available",
                                        // repair_po_reference: every_line_po[row.line_id] ,
                                        stock_entry_reference: cur_frm.doc.name,
                                        asset_repair_reference: last_window_asset_repair,
                                        asset_reference: row.asset,
                                        entry_details: `Spare item (${row.spare_part}) was sent for repair.
                                        Source Warehouse: ${row.source_warehouse}
                                        Target Warehouse: ${row.target_warehouse}
                                        Repair Start Date: ${entry_date}
                                        Workstation: ${spare_entry_doc.workstation}
                                        Reference Line ID: ${row.line_id}
                                        Serial No: ${row.serial_no || "N/A"}
                                        Stock Entry Reference: ${cur_frm.doc.name}
                                        Note: Item has been moved out of the workstation and transferred to the repair store for maintenance work.`
                                    };
                                    frappe.call({
                                        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
                                        args: {
                                            data: move_history_data
                                        },
                                        callback: function (r) {
                                            if (r.message) {
                                                // frappe.call({
                                                //     method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.update_spare_status",
                                                //     args: {
                                                //         docname: row.line_id,
                                                //         //new_status: "Available"
                                                //     }
                                                // });
                                                frappe.msgprint(__("Spare Move History Log created: ") + r.message);
                                            } else {
                                                frappe.msgprint(__("Spare Move History Log creation failed or returned no id."));
                                            }
                                        }
                                    })
                                })
                            })
                        }, 1000);
                    }
                    d.hide();
                }
            });
            // Setup sync for fields
                const field_mappings = [
                    { parent: 'default_target_warehouse', child: 'target_warehouse' },
                ];
                // Apply sync for warehouse
                add_sync_field_to_child_table(
                    d,
                    { fieldname: 'default_target_warehouse', label: 'Default Target Warehouse', fieldtype: 'Link' },
                    'spares_details_for_stock_entry',
                    field_mappings
                );
            if (all_selected_docs.length>0){
                d.show();
            }
        }).hide();


        // ================================== Damaged Button  ===================================== 

        let damaged_btn = listview.page.add_action_item(__("Damaged"), async () => {
            if (!damaged_warehouse){
                settings_not_found_validation_check("Default Damaged Items Warehouse")
            }
            let selected_rows_names = listview.get_checked_items();
            let all_selected_docs = []
            let selected_rows_names_list = []
            for (const selected_row of selected_rows_names) {
                selected_rows_names_list.push(selected_row.name)
            }
            // console.log('===== here is the selected_rows_names_list  = ', selected_rows_names_list)
            await check_spare_history_and_stock_entry(selected_rows_names_list,all_selected_docs)
            
            const spare_table_data = all_selected_docs.map(row_doc => {
                return {
                    source_warehouse: row_doc.source_warehouse,
                    target_warehouse: damaged_warehouse,
                    spare_part: row_doc.spare_part,
                    entry_date: today_date,
                    line_id: row_doc.name ,
                    serial_no: row_doc.item_serial_number,
                    asset:row_doc.asset_reference
                    // maintenance_responsible_party :
                };
            })
            let d = new frappe.ui.Dialog({
                title: 'Enter Detials: Damaged Spares',
                size: 'extra-large',
                fields: [
                    { label: 'Entry Date', fieldname: 'entry_date', fieldtype: 'Date',default:today_date, in_list_view: 1, "reqd": 1 },
                    {
                        label: 'Default Target Warehouse',
                        fieldname: 'default_target_warehouse',
                        fieldtype: 'Link',
                        options: 'Warehouse',
                        description: 'This warehouse will be applied to all rows below',
                        default:damaged_warehouse,
                    },
                    {
                        fieldname: 'column_break_1',
                        fieldtype: 'Column Break'
                    },
                    {
                        fieldname: 'section_break_1',
                        fieldtype: 'Section Break',
                        label: 'Spares Details'
                    },
                    {
                        label: 'Spares Details For Stock Entry',
                        fieldname: 'spares_details_for_stock_entry',
                        fieldtype: 'Table',
                        cannot_add_rows: true,
                        in_place_edit: false,
                        data: spare_table_data,
                        fields: [
                            { label: 'Source Warehouse', fieldname: 'source_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, width: 150, "reqd": 1, read_only: true },
                            {
                                label: 'Target Warehouse', fieldname: 'target_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, "reqd": 1, 
                            },
                            { label: 'Spare Part', fieldname: 'spare_part', fieldtype: 'Link', options: 'Item', in_list_view: 1, read_only: true, "reqd": 1 },
                            // { label: 'Repair Responsible Party', fieldname: 'repair_responsible_party', fieldtype: 'Link',options:'Supplier', in_list_view: 1 },
                            { label: 'Serial No.', fieldname: 'serial_no', fieldtype: 'Data', in_list_view: 1, width: '10%', "reqd": 1, read_only: true },
                            { 
                                label: 'Line Id', 
                                fieldname: 'line_id', 
                                fieldtype: 'Link', 
                                options: 'Workstation Spare Parts', 
                                in_list_view: 1 ,
                                read_only: true 
                            },
                            { 
                                label: 'Asset', 
                                fieldname: 'asset', 
                                fieldtype: 'Link', 
                                options: 'Asset', 
                                in_list_view: 0,
                                read_only: true
                            },
                        ]
                    },
                ],
                primary_action_label: 'Create Stock Entry',
                primary_action: async (values) => {
                    await validate_required_table_fields(
                        d,                               
                        "spares_details_for_stock_entry",
                        values.spares_details_for_stock_entry 
                    );
                    let entry_date = values.entry_date
                    let stk_entry_type = "Material Transfer";
                    frappe.set_route("Form", "Stock Entry", "new-stock-entry-1");
                    setTimeout(async() => {
                        if (cur_frm && cur_frm.doc.doctype === "Stock Entry") {
                            cur_frm.set_value("stock_entry_type", stk_entry_type);
                            cur_frm.set_value("custom_stock_entry_reference", listview.doctype);
                            // cur_frm.set_value("to_warehouse", to_warehouse);
                            // cur_frm.set_value("from_warehouse", from_warehouse);
                            cur_frm.set_value("set_posting_time", 1);
                            cur_frm.set_value("posting_date" , entry_date);
                            cur_frm.set_value("remarks", last_window_asset_repair || "");
                            // cur_frm.set_value("custom_stock_item_move_reference",frm.doc.name );
                            cur_frm.clear_table("items");

                            (async () => {
                                for (const row of values.spares_details_for_stock_entry){
                                    // cur_frm.set_value("posting_date", row.entry_date);
                                    // Get item UOM
                                    const r = await frappe.db.get_value('Item', row.spare_part, 'stock_uom');
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        continue;
                                    }
                                    let item_uom = r.message.stock_uom;
                                    let child = cur_frm.add_child("items", {
                                        s_warehouse: row.source_warehouse,
                                        t_warehouse: row.target_warehouse,
                                        item_code: row.spare_part,
                                        qty: 1,
                                        transfer_qty: 1,
                                        uom: item_uom,
                                        stock_uom: item_uom,
                                        conversion_factor: 1,
                                        use_serial_batch_fields: 1,
                                        serial_no: row.serial_no,
                                        custom_stock_item_move_reference: row.line_id
                                    });
                                }
                                cur_frm.refresh_field("items");
                                cur_frm.refresh();
                                await cur_frm.save();
                                run();
                            })();
                        }
                    }, 600);
                    //  =================== Spare Move History Log Creation =========================== //
                    // 
                    function run() {
                        setTimeout(() => {
                            values.spares_details_for_stock_entry.forEach(async row => {
                                spare_entry_doc = await frappe.db.get_doc("Workstation Spare Parts", row.line_id)
                                // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                frappe.db.get_value('Item', row.spare_part, 'stock_uom').then(r => {
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        return;
                                    }
                                    // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                    let move_history_data = {
                                        spare_entry_reference: row.line_id,
                                        workstation: spare_entry_doc.workstation,
                                        spare_part: row.spare_part,
                                        from_warehouse: row.source_warehouse,
                                        to_warehouse: row.target_warehouse,
                                        entry_date: entry_date,
                                        old_status: spare_entry_doc.spare_status,
                                        current_status: "Damaged",
                                        // repair_po_reference: every_line_po[row.line_id] ,
                                        stock_entry_reference: cur_frm.doc.name,
                                        asset_repair_reference: last_window_asset_repair,
                                        asset_reference: row.asset,
                                        entry_details: `Spare item (${row.spare_part}) was Damaged.
                                        Source Warehouse: ${row.source_warehouse}
                                        Target Warehouse: ${row.target_warehouse}
                                        Repair Start Date: ${entry_date}
                                        Workstation: ${spare_entry_doc.workstation}
                                        Reference Line ID: ${row.line_id}
                                        Serial No: ${row.serial_no || "N/A"}
                                        Stock Entry Reference: ${cur_frm.doc.name}
                                        Note: Item has been moved out of the workstation and transferred to the damaged store for maintenance work.`
                                    };
                                    frappe.call({
                                        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
                                        args: {
                                            data: move_history_data
                                        },
                                        callback: function (r) {
                                            if (r.message) {
                                                // frappe.call({
                                                //     method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.update_spare_status",
                                                //     args: {
                                                //         docname: row.line_id,
                                                //         //new_status: "Available"
                                                //     }
                                                // });
                                                frappe.msgprint(__("Spare Move History Log created: ") + r.message);
                                            } else {
                                                frappe.msgprint(__("Spare Move History Log creation failed or returned no id."));
                                            }
                                        }
                                    })
                                })
                            })
                        }, 1000);
                    }
                    d.hide();
                }
            });
            // Setup sync for fields
                const field_mappings = [
                    { parent: 'default_target_warehouse', child: 'target_warehouse' },
                ];
                // Apply sync for warehouse
                add_sync_field_to_child_table(
                    d,
                    { fieldname: 'default_target_warehouse', label: 'Default Target Warehouse', fieldtype: 'Link' },
                    'spares_details_for_stock_entry',
                    field_mappings
                );
            if (all_selected_docs.length>0){
                d.show();
            }
        }).hide();




        // ================================== Install On Same MACHINE from Status Available  ===================================== 

        let install_on_machine_btn = listview.page.add_action_item(__("Install On Same Machine"), async () => {
            let selected_rows_names = listview.get_checked_items();
            let all_selected_docs = []
            let selected_rows_names_list = []
            for (const selected_row of selected_rows_names) {
                selected_rows_names_list.push(selected_row.name)
            }
            // console.log('===== here is the selected_rows_names_list  = ', selected_rows_names_list)
            await check_spare_history_and_stock_entry(selected_rows_names_list,all_selected_docs)
            
            const spare_table_data = all_selected_docs.map(row_doc => {
                return {
                    source_warehouse: row_doc.source_warehouse,
                    target_warehouse: row_doc.target_warehouse,
                    spare_part: row_doc.spare_part,
                    entry_date: today_date,
                    line_id: row_doc.name ,
                    serial_no: row_doc.item_serial_number,
                    asset:row_doc.asset_reference
                    // maintenance_responsible_party :
                };
            })
            let d = new frappe.ui.Dialog({
                title: 'Enter Spares Detials: Install On Same Machine',
                size: 'extra-large',
                fields: [
                    { label: 'Entry Date', fieldname: 'entry_date', fieldtype: 'Date',default:today_date, in_list_view: 1, "reqd": 1 },
                                {
                                    fieldname: 'column_break_1',
                                    fieldtype: 'Column Break'
                                },
                                {
                                    fieldname: 'section_break_1',
                                    fieldtype: 'Section Break',
                                    label: 'Spares Details'
                                },
                    {
                        label: 'Spares Details For Stock Entry',
                        fieldname: 'spares_details_for_stock_entry',
                        fieldtype: 'Table',
                        cannot_add_rows: true,
                        in_place_edit: false,
                        data: spare_table_data,
                        fields: [
                            { label: 'Source Warehouse', fieldname: 'source_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, width: 150, "reqd": 1, read_only: true },
                            {
                                label: 'Target Warehouse', fieldname: 'target_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, "reqd": 1,read_only:true },
                            { label: 'Spare Part', fieldname: 'spare_part', fieldtype: 'Link', options: 'Item', in_list_view: 1, read_only: true, "reqd": 1 },
                            // { label: 'Repair Responsible Party', fieldname: 'repair_responsible_party', fieldtype: 'Link',options:'Supplier', in_list_view: 1 },
                            { label: 'Serial No.', fieldname: 'serial_no', fieldtype: 'Data', in_list_view: 1, width: '10%', "reqd": 1, read_only: true },
                            { 
                                label: 'Line Id', 
                                fieldname: 'line_id', 
                                fieldtype: 'Link', 
                                options: 'Workstation Spare Parts', 
                                in_list_view: 1 ,
                                read_only: true 
                            },
                            { 
                                label: 'Asset', 
                                fieldname: 'asset', 
                                fieldtype: 'Link', 
                                options: 'Asset', 
                                in_list_view: 0,
                                read_only: true
                            },
                        ]
                    },
                ],
                primary_action_label: 'Create Stock Entry',
                primary_action: async (values) => {
                    await validate_required_table_fields(
                        d,                               
                        "spares_details_for_stock_entry",
                        values.spares_details_for_stock_entry 
                    );
                    let entry_date = values.entry_date;
                    let stk_entry_type = "Material Transfer";
                    frappe.set_route("Form", "Stock Entry", "new-stock-entry-1");
                    setTimeout(async () => {
                        if (cur_frm && cur_frm.doc.doctype === "Stock Entry") {
                            cur_frm.set_value("stock_entry_type", stk_entry_type);
                            cur_frm.set_value("custom_stock_entry_reference", listview.doctype);
                            // cur_frm.set_value("to_warehouse", to_warehouse);
                            // cur_frm.set_value("from_warehouse", from_warehouse);
                            cur_frm.set_value("set_posting_time", 1);
                            cur_frm.set_value("posting_date" , entry_date);
                            cur_frm.set_value("remarks", last_window_asset_repair || "");
                            // cur_frm.set_value("custom_stock_item_move_reference",frm.doc.name );
                            cur_frm.clear_table("items");
                            (async () => {
                                for (const row of values.spares_details_for_stock_entry){                                    // cur_frm.set_value("posting_date" , entry_date);
                                    // Get item UOM
                                    const r = await frappe.db.get_value('Item', row.spare_part, 'stock_uom');
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        continue;
                                    }
                                    let item_uom = r.message.stock_uom;
                                    let child = cur_frm.add_child("items", {
                                        s_warehouse: row.source_warehouse,
                                        t_warehouse: row.target_warehouse,
                                        item_code: row.spare_part,
                                        qty: 1,
                                        transfer_qty: 1,
                                        uom: item_uom,
                                        stock_uom: item_uom,
                                        conversion_factor: 1,
                                        use_serial_batch_fields: 1,
                                        serial_no: row.serial_no,
                                        custom_stock_item_move_reference: row.line_id
                                    });
                                }
                                cur_frm.refresh_field("items");
                                cur_frm.refresh();
                                await cur_frm.save();
                                run();
                            })();
                        }
                    }, 1000);
                    //  =================== Spare Move History Log Creation =========================== //
                    // 
                    function run() {
                        setTimeout(() => {
                            values.spares_details_for_stock_entry.forEach(async row => {
                                spare_entry_doc = await frappe.db.get_doc("Workstation Spare Parts", row.line_id)
                                // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                frappe.db.get_value('Item', row.spare_part, 'stock_uom').then(r => {
                                    if (!r.message) {
                                        frappe.msgprint("Item UOM not found");
                                        return;
                                    }
                                    // console.log('herei is the dpare entry doc = ', spare_entry_doc)
                                    let move_history_data = {
                                        spare_entry_reference: row.line_id,
                                        workstation: spare_entry_doc.workstation,
                                        spare_part: row.spare_part,
                                        from_warehouse: row.source_warehouse,
                                        to_warehouse: row.target_warehouse,
                                        entry_date: entry_date,
                                        old_status: spare_entry_doc.spare_status,
                                        current_status: "In Use",
                                        // repair_po_reference: every_line_po[row.line_id] ,
                                        stock_entry_reference: cur_frm.doc.name,
                                        asset_repair_reference: last_window_asset_repair,
                                        asset_reference: row.asset,
                                        entry_details: `Spare item (${row.spare_part}) was sent for repair.
                                        Source Warehouse: ${row.source_warehouse}
                                        Target Warehouse: ${row.target_warehouse}
                                        Repair Start Date: ${entry_date}
                                        Workstation: ${spare_entry_doc.workstation}
                                        Reference Line ID: ${row.line_id}
                                        Serial No: ${row.serial_no || "N/A"}
                                        Stock Entry Reference: ${cur_frm.doc.name}
                                        Note: Item has been moved out of the workstation and transferred to the repair store for maintenance work.`
                                    };
                                    frappe.call({
                                        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
                                        args: {
                                            data: move_history_data
                                        },
                                        callback: function (r) {
                                            if (r.message) {
                                                // frappe.call({
                                                //     method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.update_spare_status",
                                                //     args: {
                                                //         docname: row.line_id,
                                                //         //new_status: "In Use"
                                                //     }
                                                // });
                                                frappe.msgprint(__("Spare Move History Log created: ") + r.message);
                                            } else {
                                                frappe.msgprint(__("Spare Move History Log creation failed or returned no id."));
                                            }
                                        }
                                    })
                                })
                            })
                        }, 1000);
                    }
                    d.hide();
                }
            });
            if (all_selected_docs.length>0){
                d.show();
            }

        }).hide();


        // ================================== Install On Other MACHINE from Status Available  ===================================== 

        let install_on_other_machine_btn = listview.page.add_action_item("Install On Other Machine", async () => {
            let selected_rows_names = listview.get_checked_items();
            let all_selected_docs = [];
            
            let selected_rows_names_list = []
            for (const selected_row of selected_rows_names) {
                selected_rows_names_list.push(selected_row.name)
            }
            // console.log('===== here is the selected_rows_names_list  = ', selected_rows_names_list)
            await check_spare_history_and_stock_entry(selected_rows_names_list,all_selected_docs)
            // Prepare table data for dialog
            const spare_table_data = all_selected_docs.map(row_doc => {
                return {
                    source_warehouse: row_doc.source_warehouse,
                    // workstation: row_doc.workstation,
                    spare_part: row_doc.spare_part,
                    entry_date: today_date,
                    line_id: row_doc.name ,
                    serial_no: row_doc.item_serial_number,
                    // asset:row_doc.asset_reference
                };
            });
            
            // Show dialog
            let d = new frappe.ui.Dialog({
                title: 'Enter Spares Details: Install On Other Machine',
                size: 'extra-large',
                fields: [
                    {
                        label: 'Spares Details For Stock Entry',
                        fieldname: 'spares_details_for_stock_entry',
                        fieldtype: 'Table',
                        cannot_add_rows: true,
                        in_place_edit: false,
                        data: spare_table_data,
                        fields: [
                            {
                                label: 'Select Workstation',
                                fieldname: 'workstation',
                                fieldtype: 'Link',
                                options: 'Workstation',
                                in_list_view: 1,
                                width: 150,
                                reqd: 1
                            },
                            {
                                label: 'Source Warehouse',
                                fieldname: 'source_warehouse',
                                fieldtype: 'Link',
                                options: 'Warehouse',
                                in_list_view: 1,
                                width: 150,
                                reqd: 1,
                                read_only: 1
                            },
                            {
                                label: 'Target Warehouse',
                                fieldname: 'target_warehouse',
                                fieldtype: 'Link',
                                options: 'Warehouse',
                                in_list_view: 1,
                                reqd: 1
                            },
                            {
                                label: 'Entry Date',
                                fieldname: 'entry_date',
                                fieldtype: 'Date',
                                in_list_view: 1,
                                reqd: 1
                            },
                            {
                                label: 'Spare Part',
                                fieldname: 'spare_part',
                                fieldtype: 'Link',
                                options: 'Item',
                                in_list_view: 1,
                                read_only: 1,
                                reqd: 1
                            },
                            {
                                label: 'Serial No.',
                                fieldname: 'serial_no',
                                fieldtype: 'Data',
                                in_list_view: 1,
                                width: '10%',
                                reqd: 1,
                                read_only: 1
                            },
                            { 
                                label: 'Asset', 
                                fieldname: 'asset', 
                                fieldtype: 'Link', 
                                options: 'Asset', 
                                in_list_view: 1,
                                reqd: 1,
                                // read_only: 
                            },
                            {
                                label: 'Line Id',
                                fieldname: 'line_id',
                                fieldtype: 'Link',
                                options: 'Workstation Spare Parts',
                                in_list_view: 1,
                                read_only: 1
                            },
                        ]
                    },
                ],
                primary_action_label: 'Create Workstation Spare Entries',
                primary_action: async (values) => {
                    await validate_required_table_fields(
                        d,                               
                        "spares_details_for_stock_entry",
                        values.spares_details_for_stock_entry 
                    );
                    try {
                        const rows = values.spares_details_for_stock_entry;

                        if (rows.length === 1) {
                            // Single record - Create and show the form
                            await createSingleWorkstationSpareEntry(rows[0]);
                        } else {
                            // Multiple records - Create all entries in background
                            await createMultipleWorkstationSpareEntries(rows);
                        }

                        d.hide();
                    } catch (error) {
                        console.error("Error in primary action:", error);
                        frappe.msgprint(`Error: ${error.message}`);
                    }
                }
            });
            if (all_selected_docs.length>0){
                d.show();
            }
            d.fields_dict.spares_details_for_stock_entry.grid.wrapper
                .on('change', 'input[data-fieldname="workstation"], .link-field[data-fieldname="workstation"]', async function (e) {
                    // console.log('-------------------------------- cahl gya ')
                    let row = $(e.target).closest(".grid-row").data("row");
                    let workstation = row.workstation;

                    if (!workstation) return;

                    // Fetch workstation doc
                    let ws = await frappe.db.get_doc("Workstation", workstation);

                    if (!ws) {
                        frappe.msgprint(`Workstation <b>${workstation}</b> not found`);
                        return;
                    }

                    // Validate warehouse
                    if (!ws.warehouse) {
                        frappe.msgprint({
                            title: 'Configuration Missing',
                            indicator: 'red',
                            message: `Warehouse not configured for workstation <b>${workstation}</b>. Please configure it first.`
                        });
                        row.workstation = null;
                        d.fields_dict.spares_details_for_stock_entry.grid.refresh();
                        return;
                    }

                    // Validate custom_asset
                    if (!ws.custom_asset) {
                        frappe.msgprint({
                            title: 'Configuration Missing',
                            indicator: 'red',
                            message: `Asset not configured for workstation <b>${workstation}</b>. Please configure it first.`
                        });
                        row.workstation = null;
                        d.fields_dict.spares_details_for_stock_entry.grid.refresh();
                        return;
                    }

                    // Set values in row
                    row.target_warehouse = ws.warehouse;
                    row.asset = ws.custom_asset;

                    // Refresh table row
                    d.fields_dict.spares_details_for_stock_entry.grid.refresh();
                });

        }).hide();
        // // ================================== Install On Other MACHINE from Status Available  ===================================== 

        // let install_on_other_machine_btn = listview.page.add_action_item("Install On Other Machine", async () => {
        //     let selected_rows_names = listview.get_checked_items();
        //     let all_selected_docs = []
        //             
        //     for (const selected_row of selected_rows_names) {
        //         try {
        //             let spare_doc = await frappe.db.get_doc("Workstation Spare Parts", selected_row.name)
        //             let move_history_list = await frappe.db.get_list("Spares Move History", {
        //                 fields: ['*'],
        //                 filters: {
        //                     'spare_entry_reference': spare_doc.name
        //                 },
        //                 limit: 1,
        //                 order_by: "creation desc"
        //             });

        //             if (!move_history_list.length) {
        //                 frappe.msgprint(`No move history found for Spare: <b>${spare_doc.name}</b>`);
        //                 return;
        //             }

        //             let latest_history = move_history_list[0];
        //             // console.log("here is the latest hsitory ==", latest_history)
        //             const r = await frappe.db.get_value(
        //                 'Stock Entry',
        //                 latest_history.stock_entry_reference,
        //                 'docstatus'
        //             );
        //             if (!r.message) {
        //                 frappe.msgprint("Failed to fetch Docstatus of Stock Entry!");
        //                 return;
        //             }

        //             let docstatus = r.message.docstatus;

        //             if (docstatus == 0) {
        //                 frappe.msgprint(`
        //                         <b>Stock Entry Not Submitted!</b><br><br>
        //                         Spare Entry: <b>${spare_doc.name}</b><br>
        //                         Stock Entry: <b>${latest_history.stock_entry_reference}</b><br><br>
        //                         This Stock Entry is not submitted yet. Please submit it first or Cancel it.
        //                     `);

        //                 return;
        //             }
        //             // console.log("Stock Entry submitted, proceed:", latest_history);
        //             let serial_no_doc = await frappe.db.get_doc("Serial No", spare_doc.item_serial_number)
        //             spare_doc.source_warehouse = serial_no_doc.warehouse
        //             all_selected_docs.push(spare_doc)
        //             // console.log('inside teh loop yeeey-- here is the all_selected_docs ==',spare_doc.source_warehouse)    
        //         } catch (error) {
        //             console.error('Error fetching doc:', error);
        //         }
        //     }
        //     const spare_table_data = all_selected_docs.map(row_doc => {
        //         return {
        //             source_warehouse: row_doc.source_warehouse,
        //             // target_warehouse: "",
        //             workstation: row_doc.workstation,
        //             spare_part: row_doc.spare_part,
        //             entry_date: today_date,
        //             line_id: row_doc.name,
        //             serial_no: row_doc.item_serial_number
        //             // maintenance_responsible_party :
        //         };
        //     })
        //     let d = new frappe.ui.Dialog({
        //         title: 'Enter Spares Detials: Install On Machine',
        //         size: 'extra-large',
        //         fields: [
        //             {
        //                 label: 'Spares Details For Stock Entry',
        //                 fieldname: 'spares_details_for_stock_entry',
        //                 fieldtype: 'Table',
        //                 cannot_add_rows: true,
        //                 in_place_edit: false,
        //                 data: spare_table_data,
        //                 fields: [
        //                     { label: 'Select Workstation', fieldname: 'workstation', fieldtype: 'Link', options: 'Workstation', in_list_view: 1, width: 150, "reqd": 1 },

        //                     { label: 'Source Warehouse', fieldname: 'source_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, width: 150, "reqd": 1, read_only: true },
        //                     {
        //                         label: 'Target Warehouse', fieldname: 'target_warehouse', fieldtype: 'Link', options: 'Warehouse', in_list_view: 1, "reqd": 1, get_query: () => {
        //                             // return {
        //                             //     filters: {
        //                             //         // name: ['like', '%repair%'],
        //                             //         custom_is_spares_warehouse: false
        //                             //     }
        //                             // }
        //                         }
        //                     },
        //                     { label: 'Entry Date', fieldname: 'entry_date', fieldtype: 'Date', in_list_view: 1, "reqd": 1 },
        //                     { label: 'Spare Part', fieldname: 'spare_part', fieldtype: 'Link', options: 'Item', in_list_view: 1, read_only: true, "reqd": 1 },
        //                     // { label: 'Repair Responsible Party', fieldname: 'repair_responsible_party', fieldtype: 'Link',options:'Supplier', in_list_view: 1 },
        //                     { label: 'Serial No.', fieldname: 'serial_no', fieldtype: 'Data', in_list_view: 1, width: '10%', "reqd": 1, read_only: true },
        //                     { label: 'Line Id', fieldname: 'line_id', fieldtype: 'Link', options: 'Workstation Spare Parts', in_list_view: 1, read_only: 1 },
        //                 ]
        //             },
        //         ],
        //         primary_action_label: 'Create Other Workstation Spare Entry',
        //         primary_action: async (values) => {
        //             // let         ;
        //             // let stk_entry_type = "Material Transfer";
        //             frappe.set_route("Form", "Workstation Spare Parts", "new-workstation-spare-entry-1");
        //             setTimeout(async () => {
        //                 if (cur_frm && cur_frm.doc.doctype === "Workstation Spare Parts") {
        //                     cur_frm.set_value("workstation", values.workstation);
        //                     cur_frm.set_value("spare_part", spare_part);
        //                     // cur_frm.set_value("spare_status", spare_part)
        //                     cur_frm.set_value("source_warehouse", source_warehouse);
        //                     cur_frm.set_value("target_warehouse", target_warehouse);
        //                     cur_frm.set_value("date_of_installation", 1);
        //                     cur_frm.set_value("posting_date" , entry_date);
                            // cur_frm.set_value("remarks", last_window_asset_repair || "");
        //                     cur_frm.set_value("item_serial_number", serial_no);
        //                     cur_frm.set_value("other_workstation_spare_link", line_id);
        //                     // 
        //                     // cur_frm.set_value("custom_stock_item_move_reference",frm.doc.name );
        //                     // cur_frm.clear_table("items");

        //                     cur_frm.refresh();
        //                     await cur_frm.save();
        //                     run();
        //                 }
        //             }, 800);
        //             //  =================== Spare Move History Log Creation =========================== //
        //             // 
        //             function run() {
        //                 setTimeout(() => {
        //                     values.spares_details_for_stock_entry.forEach(async row => {
        //                         spare_entry_doc = await frappe.db.get_doc("Workstation Spare Parts", row.line_id)
        //                         // console.log('herei is the dpare entry doc = ', spare_entry_doc)
        //                         // console.log('herei is the dpare entry doc = ', spare_entry_doc)
        //                         let move_history_data = {
        //                             spare_entry_reference: row.line_id,
        //                             workstation: spare_entry_doc.workstation,
        //                             spare_part: row.spare_part,
        //                             from_warehouse: row.source_warehouse,
        //                             to_warehouse: row.target_warehouse,
        //                             entry_date: row.entry_date,
        //                             old_status: spare_entry_doc.spare_status,
        //                             current_status: "Used In another Workstation",
        //                             // stock_entry_reference: cur_frm.doc.name,
        //                             entry_details: `Spare item (${row.spare_part}) was sent for repair.
        //                                 Source Warehouse: ${row.source_warehouse}
        //                                 Target Warehouse: ${row.target_warehouse}
        //                                 Repair Start Date: ${row.entry_date}
        //                                 Workstation: ${spare_entry_doc.workstation}
        //                                 Reference Line ID: ${row.line_id}
        //                                 Serial No: ${row.serial_no || "N/A"}
        //                                 Stock Entry Reference: ${cur_frm.doc.name}
        //                                 Note: Item has been moved out of the workstation and transferred to the repair store for maintenance work.`
        //                         };
        //                         frappe.call({
        //                             method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
        //                             args: {
        //                                 data: move_history_data
        //                             },
        //                             callback: function (r) {
        //                                 if (r.message) {
        //                                     frappe.call({
        //                                         method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.update_spare_status",
        //                                         args: {
        //                                             docname: row.line_id,
        //                                             new_status: "Used In another Workstation"
        //                                         }
        //                                     });
        //                                     frappe.msgprint(__("Spare Move History Log created: ") + r.message);
        //                                 } else {
        //                                     frappe.msgprint(__("Spare Move History Log creation failed or returned no id."));
        //                                 }
        //                             }
        //                         })
        //                     })
        //                 }, 1000);
        //             }
        //             d.hide();
        //         }
        //     });
        //     d.show();

        // }).hide();

        // Common function to update button visibility
    function updateButtonVisibility() {
        let selected = listview.get_checked_items();
        
        // Hide all buttons initially
        const hideAllButtons = () => {
            send_for_repair_btn.hide();
            remove_from_machine_btn.hide();
            recieve_in_warehouse_btn.hide();
            reinstall_on_machine_btn.hide();
            scrap_btn.hide();
            install_on_machine_btn.hide();
            install_on_other_machine_btn.hide();
            damaged_btn.hide();

        };

        if (selected.length === 0) {
            hideAllButtons();
            return;
        }

        hideAllButtons();

        // let all_sent_for_repair = selected.every(r => (r.spare_status === "Sent For Repair" && r.docstatus == 1));
        let all_in_use = selected.every(r => r.spare_status === "In Use" && r.docstatus == 1);
        let all_available = selected.every(r => r.spare_status === "Available" && r.docstatus == 1);
        let all_damaged = selected.every(r => r.spare_status === "Damaged" && r.docstatus == 1);
        if (all_in_use) {
            // send_for_repair_btn.show();
            damaged_btn.show();
            remove_from_machine_btn.show();
            scrap_btn.show();
        }
        // else if (all_sent_for_repair) {
        //     recieve_in_warehouse_btn.show();
        //     reinstall_on_machine_btn.show();
        //     scrap_btn.show();
        // }
        else if (all_damaged) {
            send_for_repair_btn.show();
            // recieve_in_warehouse_btn.show();
            // reinstall_on_machine_btn.show();
            scrap_btn.show();
        }
        else if (all_available) {
            // send_for_repair_btn.show();
            scrap_btn.show();
            install_on_machine_btn.show();
            install_on_other_machine_btn.show();
        }
    }
    $(document).on('shown.bs.dropdown', '.page-actions', async function() {
        // console.log('============================== shown.bs.dropdown')
            await updateButtonVisibility();
    });

    listview.$page.on("change", '.list-row-checkbox', function () {
        updateButtonVisibility();
    });

    listview.$page.on("change", '.list-select-all', function () {
        updateButtonVisibility();
    });

    $(document).on('page-change',async function() {
        await updateButtonVisibility();
    });
    //     listview.$page.on("change", '.list-row-checkbox', function () {

    //         let selected = listview.get_checked_items();
    //         // console.log('here is the selected items => ',selected)
    //         if (selected.length === 0) return;

    //         send_for_repair_btn.hide();
    //         let all_sent_for_repair = selected.every(r => (r.spare_status === "Sent For Repair" && r.docstatus == 1));
    //         let all_in_use = selected.every(r => r.spare_status === "In Use" && r.docstatus == 1);
    //         let all_available = selected.every(r => r.spare_status === "Available" && r.docstatus == 1);

    //         // let all_ = selected.every(r => r.spare_status === "");

    //         // send_for_repair_btn.show();

    //         if (all_in_use) {
    //             // console.log('heeeeyeey all inu se ',all_in_use)
    //             send_for_repair_btn.show();
    //             scrap_btn.show();
    //             remove_from_machine_btn.show();
    //         }
    //         else if (all_sent_for_repair) {
    //             // console.log('heeeeyeey all inu all_sent_for_repair== ',all_sent_for_repair)

    //             recieve_in_warehouse_btn.show();
    //             reinstall_on_machine_btn.show();
    //             scrap_btn.show();
    //         }

    //         else if (all_available) {
    //             // console.log('heeeeyeey all inu all_available== ',all_available)
    //             send_for_repair_btn.show();

    //             scrap_btn.show();
    //             install_on_machine_btn.show();
    //             install_on_other_machine_btn.show();
    //         }
    //         else {
    //             // console.log('heeeeyeey all inu elseeseeeee == ')

    //             send_for_repair_btn.hide();
    //             remove_from_machine_btn.hide();
    //             recieve_in_warehouse_btn.hide();
    //             reinstall_on_machine_btn.hide();

    //             scrap_btn.hide();
    //             install_on_machine_btn.hide();
    //             install_on_other_machine_btn.hide();
    //         }
    //     }
    // )
    }
};


function arrange_buttons(listview){
    
}


//  function to create single workstation spare entry
async function createSingleWorkstationSpareEntry(row) {
    try {
        // Create new Workstation Spare Parts entry
        const new_spare_entry = await createWorkstationSpareEntry(row);

        if (!new_spare_entry) {
            frappe.msgprint("Failed to create Workstation Spare Entry");
            return;
        }

        // Create move history for old entry
        await createMoveHistoryForOldEntry(row, new_spare_entry.name);

        // Show the created entry
        frappe.set_route("Form", "Workstation Spare Parts", new_spare_entry.name);
        frappe.show_alert({
            message: `Workstation Spare Entry created: ${new_spare_entry.name}`,
            indicator: 'green'
        });

    } catch (error) {
        console.error("Error creating single entry:", error);
        throw error;
    }
}

//  function to create multiple workstation spare entries
async function createMultipleWorkstationSpareEntries(rows) {
    try {
        frappe.show_progress('Creating Workstation Spare Entries', 0, rows.length);

        let created_entries = [];
        let failed_entries = [];

        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];
            try {

                const new_spare_entry = await createWorkstationSpareEntry(row);

                if (new_spare_entry) {
                    await createMoveHistoryForOldEntry(row, new_spare_entry.name);
                    created_entries.push({
                        old_entry: row.line_id,
                        new_entry: new_spare_entry.name,
                        workstation: row.workstation,
                        spare_part: row.spare_part,
                        asset_reference : row.asset,
                        asset_repair_reference : last_window_asset_repair || ""
                    });
                } else {
                    failed_entries.push(row.line_id);
                }
            } catch (error) {
                console.error(`Error creating entry for ${row.line_id}:`, error);
                failed_entries.push(row.line_id);
            }

            frappe.show_progress('Creating Workstation Spare Entries', i + 1, rows.length);
        }

        frappe.hide_progress();

        showCreationSummary(created_entries, failed_entries);

    } catch (error) {
        frappe.hide_progress();
        console.error("Error creating multiple entries:", error);
        throw error;
    }
}

//  function to create workstation spare entry
async function createWorkstationSpareEntry(row) {
    return new Promise((resolve, reject) => {
        frappe.model.with_doctype('Workstation Spare Parts', () => {
            const new_doc = frappe.model.get_new_doc('Workstation Spare Parts');

            new_doc.workstation = row.workstation;
            new_doc.spare_part = row.spare_part;
            new_doc.source_warehouse = row.source_warehouse;
            new_doc.target_warehouse = row.target_warehouse;
            new_doc.date_of_installation = row.entry_date;
            new_doc.item_serial_number = row.serial_no;
            new_doc.other_workstation_spare_link = row.line_id;
            new_doc.asset_reference = row.asset;
            // new_doc.spare_status = "Installation Pending";

            frappe.call({
                method: 'frappe.client.save',
                args: {
                    doc: new_doc
                },
                callback: function (r) {
                    if (r.message) {
                        resolve(r.message);
                    } else {
                        reject(new Error("Failed to save Workstation Spare Entry"));
                    }
                },
                error: function (err) {
                    reject(err);
                }
            });
        });
    });
}

//  function to create move history for old entry
async function createMoveHistoryForOldEntry(row, new_entry_name) {
    return new Promise(async (resolve, reject) => {
        try {
            const spare_entry_doc = await frappe.db.get_doc("Workstation Spare Parts", row.line_id);

            const move_history_data = {
                spare_entry_reference: row.line_id,
                workstation: spare_entry_doc.workstation,
                spare_part: row.spare_part,
                from_warehouse: row.source_warehouse,
                to_warehouse: row.target_warehouse,
                entry_date: row.entry_date,
                old_status: spare_entry_doc.spare_status,
                asset_reference:row.asset,
                asset_repair_reference:last_window_asset_repair,
                current_status: "Used In another Workstation",
                entry_details: `Spare item (${row.spare_part}) moved to another workstation.
                    Source Warehouse: ${row.source_warehouse}
                    Target Warehouse: ${row.target_warehouse}
                    Entry Date: ${row.entry_date}
                    Original Workstation: ${spare_entry_doc.workstation}
                    New Workstation: ${row.workstation}
                    Reference Line ID: ${row.line_id}
                    New Entry Reference: ${new_entry_name}
                    Serial No: ${row.serial_no || "N/A"}
                    Note: Item has been moved to another workstation for installation.`
            };

            frappe.call({
                method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
                args: {
                    data: move_history_data
                },
                callback: function (r) {
                    if (r.message) {
                        // Update old entry status
                        frappe.call({
                            method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.update_spare_status",
                            args: {
                                docname: row.line_id,
                                new_status: "Used In another Workstation"
                            },
                            callback: function () {
                                resolve(r.message);
                            }
                        });
                    } else {
                        reject(new Error("Failed to create Move History"));
                    }
                },
                error: function (err) {
                    reject(err);
                }
            });
        } catch (error) {
            reject(error);
        }
    });
}

//  function to show creation summary
function showCreationSummary(created_entries, failed_entries) {
    let message = `<h3>Workstation Spare Entries Creation Summary</h3>`;

    if (created_entries.length > 0) {
        message += `<br><b style="color: green;">Successfully Created (${created_entries.length}):</b><br>`;
        message += `<table class="table table-bordered" style="margin-top: 10px;">
            <thead>
                <tr>
                    <th>Old Entry</th>
                    <th>New Entry</th>
                    <th>Workstation</th>
                    <th>Spare Part</th>
                </tr>
            </thead>
            <tbody>`;

        created_entries.forEach(entry => {
            message += `<tr>
                <td><a href="/app/workstation-spare-parts/${entry.old_entry}">${entry.old_entry}</a></td>
                <td><a href="/app/workstation-spare-parts/${entry.new_entry}">${entry.new_entry}</a></td>
                <td>${entry.workstation}</td>
                <td>${entry.spare_part}</td>
            </tr>`;
        });

        message += `</tbody></table>`;
    }

    if (failed_entries.length > 0) {
        message += `<br><b style="color: red;">Failed (${failed_entries.length}):</b><br>`;
        message += failed_entries.join(', ');
    }

    frappe.msgprint({
        title: 'Creation Complete',
        message: message,
        indicator: 'green',
        primary_action: {
            label: 'Refresh List',
            action: function () {
                frappe.set_route('List', 'Workstation Spare Parts');
                window.location.reload();
            }
        }
    });
}