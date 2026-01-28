// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt
// let item_uom = ""

function create_stock_entry(entry_type, from_wh, to_wh, spare_part, item_uom, ref_doc, install_date, message,spare_qty) {
    frappe.new_doc("Stock Entry", {
        stock_entry_type: entry_type,
        from_warehouse: from_wh,
        to_warehouse: to_wh || "",
        posting_date: install_date,
        set_posting_time: 1,
        custom_stock_entry_reference: ref_doc,
        remarks: message,
        spare_qty: spare_qty 
    },function(doc){
        doc.from_warehouse = from_wh;
        doc.to_warehouse = to_wh || "";
        doc.posting_date = install_date

        frappe.model.clear_table(doc, "items");
        var row = frappe.model.add_child(doc, "items"); 
        row.uom = item_uom; 
        row.stock_uom = item_uom; 
        row.conversion_factor = 1; 
        row.item_code = spare_part; 
        row.transfer_qty = spare_qty;
        row.qty = spare_qty;
        frappe.set_route("Form", "Stock Entry", doc.name);
        frappe.msgprint(`Stock Entry initiated for <b>${spare_part}</b> (${entry_type}).`);
        
    // },600);
})
}
async function createStockEntry(
    entry_type,
    workstation,
    to_warehouse,
    from_warehouse,
    posting_date,
    item_code,
    uom,
    reference_doctype,
    reference_name,
    serial_no,
    asset_repair_reference
) {
    return new Promise((resolve, reject) => {
        // Create new Stock Entry
        frappe.model.with_doctype('Stock Entry', () => {
            const stock_entry = frappe.model.get_new_doc('Stock Entry');

            stock_entry.stock_entry_type = entry_type;
            stock_entry.to_warehouse = to_warehouse;
            stock_entry.from_warehouse = from_warehouse;
            stock_entry.posting_date = posting_date;
            stock_entry.set_posting_time = 1;
            stock_entry.custom_stock_entry_reference = reference_doctype;
            stock_entry.asset_repair = asset_repair_reference
            stock_entry.custom_default_workstation = workstation

            // Add item to items table
            const item_row = frappe.model.add_child(stock_entry, 'Stock Entry Detail', 'items');
            item_row.item_code = item_code;
            item_row.qty = 1;
            item_row.transfer_qty = 1;
            item_row.uom = uom;
            item_row.stock_uom = uom;
            item_row.conversion_factor = 1;
            item_row.use_serial_batch_fields = 1;
            item_row.custom_stock_item_move_reference = reference_name;
            item_row.serial_no = serial_no
            item_row.custom_workstation = workstation
            // Save the document
            frappe.call({
                method: 'frappe.client.save',
                args: {
                    doc: stock_entry
                },
                callback: function(r) {
                    if (r.message) {
                        // Open the saved Stock Entry form
                        frappe.set_route("Form", "Stock Entry", r.message.name);
                        resolve(r.message.name);
                    } else {
                        reject(new Error("Failed to save Stock Entry"));
                    }
                },
                error: function(err) {
                    reject(err);
                }
            });
        });
    });
}

// Helper function to create Move History
async function createMoveHistory(
    spare_entry_ref,
    workstation,
    spare_part,
    from_wh,
    to_wh,
    entry_date,
    current_status,
    next_status,
    stock_entry_ref,
    from_warehouse,
    to_warehouse,
    asset,
    asset_repair
) {
    return new Promise((resolve, reject) => {
        const move_history_data = {
            spare_entry_reference: spare_entry_ref,
            workstation: workstation,
            spare_part: spare_part,
            from_warehouse: from_wh,
            to_warehouse: to_wh,
            entry_date: entry_date,
            current_status: current_status,
            next_status:next_status,
            stock_entry_reference: stock_entry_ref,
            asset_reference:asset,
            asset_repair_reference : asset_repair,
            entry_details: `Initial installation recorded for spare item (${spare_part}). 
                Transferred from ${from_warehouse} to ${to_warehouse}. 
                Commissioned at workstation on ${entry_date}.`
        };
        frappe.call({
            method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
            args: {
                data: move_history_data
            },
            callback: function(r) {
                if (r.message) {
                    resolve(r.message);
                } else {
                    reject(new Error("Failed to create Move History"));
                }
            },
            error: function(err) {
                reject(err);
            }
        });
    });
}

// frappe.ui.form.on("Spare Item Tracking Detail", {
//     spare_item_tracking_detail_add(frm, cdt, cdn) {
//         // let child = locals[cdt][cdn];
//         if (frm.doc.source_warehouse)
//             frappe.model.set_value(cdt, cdn, "source_warehouse", frm.doc.source_warehouse);

//         if (frm.doc.target_warehouse)
//             frappe.model.set_value(cdt, cdn, "target_warehouse", frm.doc.target_warehouse);

//         if (frm.doc.workstation)
//             frappe.model.set_value(cdt, cdn, "workstation", frm.doc.workstation);
//         frm.refresh_field("spare_item_tracking_detail");
//             let todayDate = frappe.datetime.get_today();

//         frappe.model.set_value(cdt, cdn, "date_of_installation", frappe.datetime.get_today());
//     },

    
// });

frappe.ui.form.on("Workstation Spare Parts", {
    

    
    workstation(frm){
        if (frm.doc.workstation){
            frappe.db.get_value("Workstation", frm.doc.workstation, ["warehouse","custom_asset"]).then(r => {
            if (!r.message.warehouse) {
                frappe.msgprint("Spare Warehouse is not set in this workstation. It is recommended to configure the warehouse first.");
                return;
            }
            if (!r.message.custom_asset) {
                    frappe.msgprint("No asset is linked to this workstation. It is recommended to configure the asset first.")
                return;
            }
            // console.log('ieiieeiei',r.message)
            frm.set_value("target_warehouse",r.message.warehouse)
            frm.set_value("asset_reference",r.message.custom_asset)

        })}
    },
    onload_post_render:function(frm){
if (frm.doc.docstatus == 0) {
            frm.set_intro(
                "This spare is being installed on this workstation. Submit this document to proceed with creating the required stock entry.",
                "blue"
            );
        }
    },
    refresh: async function (frm) {
        // Intro for draft
        
        // Only show move history decorator and button after document is submitted
        if (frm.doc.docstatus !== 1) {
            return;
        }
        
        // Fetch entire move history (latest first)
        let move_history_list = await frappe.db.get_list("Spares Move History", {
            fields: ['*'],
            filters: {
                'spare_entry_reference': frm.doc.name
            },
            order_by: "creation desc"
        });
        
        if (!move_history_list.length) {
            if (frm.doc.spare_status === "Installation Pending") {
            console.log('========================')
            frm.add_custom_button(__("Manual Initial Stock Entry"),async function () {
                try {
        // Get Item UOM
        const r = await frappe.db.get_value('Item', frm.doc.spare_part, 'stock_uom');
        
        if (!r.message) {
            frappe.msgprint("Item UOM not found");
            return;
        }

        const item_uom = r.message.stock_uom;
        const spare_part = frm.doc.spare_part;
        const to_warehouse = frm.doc.target_warehouse ;
        const from_warehouse = frm.doc.source_warehouse;
        const install_date = frm.doc.date_of_installation;
        const stk_entry_type = "Spares Consumption";
        const serial_no = frm.doc.item_serial_number || ""
        // const next_status = frm.doc.spare_status === "Installation Pending" ? "In Use" : "";
        const current_status = "Temporarily Consumed"
        const next_status = "In Use";
        const last_window_asset_repair = window.last_window_asset_repair
        const asset = frm.doc.asset || ""
        const workstation = frm.doc.workstation
        // Create and setup Stock Entry
        const stock_entry_name = await createStockEntry(
            stk_entry_type,
            workstation,
            to_warehouse,
            from_warehouse,
            install_date,
            spare_part,
            item_uom,
            frm.doc.doctype,
            frm.doc.name,
            serial_no,
            last_window_asset_repair
        );

        if (!stock_entry_name) {
            frappe.msgprint("Failed to create Stock Entry");
            return;
        }

        // Create Move History after Stock Entry is saved
        await createMoveHistory(
            frm.doc.name,
            frm.doc.workstation,
            spare_part,
            frm.doc.source_warehouse,
            frm.doc.target_warehouse,
            install_date,
            current_status,
            next_status,
            stock_entry_name,
            from_warehouse,
            to_warehouse,
            asset,
            last_window_asset_repair
        );

        frappe.msgprint("Stock Entry and Move History created successfully");

    } catch (error) {
        console.error("Error in on_submit:", error);
        frappe.msgprint(`Error: ${error.message}`);
    }
            
            });
        }
            frm.dashboard.set_headline_alert(
                `No move history found for Spare: <b>${frm.doc.name}</b>`,
                "red"
            );
            return;
        }
        
        // ERROR LIST TO SHOW ALL PROBLEMS AT ONCE
        let errors = [];
        
        // Loop on all move history
        for (const history of move_history_list) {
            /* -------------------------
               CHECK 1 → STOCK ENTRY
            -------------------------- */
            if (history.stock_entry_reference) {
                const stock = await frappe.db.get_value(
                    "Stock Entry",
                    history.stock_entry_reference,
                    ["docstatus", "name"]
                );
                if (!stock.message) {
                    errors.push(
                        `⚠️ Failed to fetch Stock Entry <a href="/app/stock-entry/${history.stock_entry_reference}" style="text-decoration: underline;"><b>${history.stock_entry_reference}</b></a>`
                    );
                } else if (stock.message.docstatus == 0) {
                    errors.push(
                        `❌ Stock Entry <a href="/app/stock-entry/${history.stock_entry_reference}" style="text-decoration: underline;"><b>${history.stock_entry_reference}</b></a> is NOT submitted`
                    );
                }
            }
            
            /* -------------------------
               CHECK 2 → REPAIR PO
            -------------------------- */
            if (history.repair_po_reference) {
                const po = await frappe.db.get_value(
                    "Purchase Order",
                    history.repair_po_reference,
                    ["docstatus", "name"]
                );
                if (!po.message) {
                    errors.push(
                        `⚠️ Failed to fetch Purchase Order <a href="/app/purchase-order/${history.repair_po_reference}" style="text-decoration: underline;"><b>${history.repair_po_reference}</b></a>`
                    );
                } else if (po.message.docstatus == 0) {
                    errors.push(
                        `❌ Repair Purchase Order <a href="/app/purchase-order/${history.repair_po_reference}" style="text-decoration: underline;"><b>${history.repair_po_reference}</b></a> is NOT submitted`
                    );
                }
            }

            /* -------------------------
                CHECK 3 → SERVICE REQUEST
                -------------------------- */
            if (history.service_request_reference) {
                const sr = await frappe.db.get_value(
                    "Service Request",
                    history.service_request_reference,
                    ["docstatus", "name", "po_created"]
                );

                if (!sr.message) {
                    errors.push(
                        `⚠️ Failed to fetch Service Request <a href="/app/service-request/${history.service_request_reference}" style="text-decoration: underline;"><b>${history.service_request_reference}</b></a>`
                    );
                } else {
                    // SR exists - check docstatus
                    if (sr.message.docstatus == 0) {
                        errors.push(
                            `❌ Service Request <a href="/app/service-request/${history.service_request_reference}" style="text-decoration: underline;"><b>${history.service_request_reference}</b></a> is NOT submitted`
                        );
                    }
                    // SR submitted - check PO created
                    else if (sr.message.docstatus == 1 && !sr.message.po_created) {
                        errors.push(
                            `⚠️ Service Request <a href="/app/service-request/${history.service_request_reference}" style="text-decoration: underline;"><b>${history.service_request_reference}</b></a> is submitted but Purchase Order NOT created yet`
                        );
                    }
                }
            } else if (history.current_status == "Sent For Repair") {
                // Status "Sent For Repair" but no SR reference at all
                errors.push(
                    `❌ Spare status is "<b>Sent For Repair</b>" but <b>No Service Request</b> is linked in Move History`
                );
            }

            // One more Care if current status is "Sent For Repair" and Service Request is linked and submitted and PO is created and PO is submitted but this history has not linked the Stock entry then give a warning for this situation and create a selection field of spare detialed status , in which we have to set its precicse status like Service request created , PO created , PO submitted , 
            // if (history.current_status == "Sent For Repair" && history.service_request_reference && !history.stock_entry_reference && ) {

            /* -------------------------
    CHECK 4 → COMPLETE REPAIR FLOW
    -------------------------- */
    if (history.current_status == "Sent For Repair" && history.service_request_reference) {
        const sr = await frappe.db.get_value(
            "Service Request",
            history.service_request_reference,
            ["docstatus", "po_created"]
        );
        
        // SR submitted + PO created
        if (sr.message && sr.message.docstatus == 1 && sr.message.po_created) {
            // Check if PO is submitted
            if (history.repair_po_reference) {
                const po = await frappe.db.get_value(
                    "Purchase Order",
                    history.repair_po_reference,
                    ["docstatus"]
                );
                
                // PO is submitted BUT no stock entry linked
                if (po.message && po.message.docstatus == 1 && !history.stock_entry_reference) {
                    errors.push(
                        `⚠️ <b>Repair Process Incomplete:</b><br>
                        → Service Request <a href="/app/service-request/${history.service_request_reference}" style="text-decoration: underline;"><b>${history.service_request_reference}</b></a> is submitted<br>
                        → Purchase Order <a href="/app/purchase-order/${history.repair_po_reference}" style="text-decoration: underline;"><b>${history.repair_po_reference}</b></a> is submitted<br>
                        → <b style="color: orange;">BUT Stock Entry NOT created/linked</b><br>
                        → Create Stock Entry to complete repair process open purchase order and create stock entry from there.`
                    );
                }
                else if (po.message && po.message.docstatus == 1 && history.stock_entry_reference && history.is_stock_entry_submitted == 1 
                    // and this history should be the last history 
                    && move_history_list[0].name == history.name
                ){
                    // This is the case where the stock is needed to be received after repair is completed
                    // So, show here a message that stock entry is submitted and spare needs to be received back
                    errors.push(
                        `ℹ️ <b>Spare Repair Stock Entry Submitted:</b><br>
                        → Service Request <a href="/app/service-request/${history.service_request_reference}" style="text-decoration: underline;"><b>${history.service_request_reference}</b></a> is submitted<br>
                        → Purchase Order <a href="/app/purchase-order/${history.repair_po_reference}" style="text-decoration: underline;"><b>${history.repair_po_reference}</b></a> is submitted<br>
                        → Stock Entry <a href="/app/stock-entry/${history.stock_entry_reference}" style="text-decoration: underline;"><b>${history.stock_entry_reference}</b></a> is submitted<br>
                        → Spare needs to be received back into stock after repair is completed, for receive open the PO`
                    );
                }
            }
        }
    }

        }

        
        /* -------------------------
           SHOW ERRORS (DECORATOR)
        -------------------------- */
        if (errors.length > 0) {
            frm.dashboard.set_headline_alert(
                `
                <b>Pending Actions Required:</b><br><br>
                ${errors.join("<br>")}
            `,
                "red"
            );
            return; // stop further execution
        }
        
        /* ----------------------------------
           Everything passed → show button
        ----------------------------------- */
        
    },
    


    // validate: function (frm) {
    //     if (frm.doc.spare_status === "Consumed" && !frm.doc.dispose_replacement_date) {
    //         frappe.throw(__('Dispose/Replacement Date is required when spare_status is Consumed.'));
    //     }
    // },



    on_submit: async function(frm){
        // await create_stock_entry_and_history_on_submit(frm);

        try {
        // Get Item UOM
        const r = await frappe.db.get_value('Item', frm.doc.spare_part, 'stock_uom');
        
        if (!r.message) {
            frappe.msgprint("Item UOM not found");
            return;
        }

        const item_uom = r.message.stock_uom;
        const spare_part = frm.doc.spare_part;
        const to_warehouse = frm.doc.target_warehouse ;
        const from_warehouse = frm.doc.source_warehouse;
        const install_date = frm.doc.date_of_installation;
        const stk_entry_type = "Spares Consumption";
        const serial_no = frm.doc.item_serial_number || ""
        // const next_status = frm.doc.spare_status === "Installation Pending" ? "In Use" : "";
        const current_status = "Temporarily Consumed"
        const next_status = "In Use";
        const last_window_asset_repair = window.last_window_asset_repair
        const asset = frm.doc.asset || ""
        const workstation = frm.doc.workstation
        // Create and setup Stock Entry
        const stock_entry_name = await createStockEntry(
            stk_entry_type,
            workstation,
            to_warehouse,
            from_warehouse,
            install_date,
            spare_part,
            item_uom,
            frm.doc.doctype,
            frm.doc.name,
            serial_no,
            last_window_asset_repair
        );

        if (!stock_entry_name) {
            frappe.msgprint("Failed to create Stock Entry");
            return;
        }

        // Create Move History after Stock Entry is saved
        await createMoveHistory(
            frm.doc.name,
            frm.doc.workstation,
            spare_part,
            frm.doc.source_warehouse,
            frm.doc.target_warehouse,
            install_date,
            current_status,
            next_status,
            stock_entry_name,
            from_warehouse,
            to_warehouse,
            asset,
            last_window_asset_repair
        );

        frappe.msgprint("Stock Entry and Move History created successfully");

    } catch (error) {
        console.error("Error in on_submit:", error);
        frappe.msgprint(`Error: ${error.message}`);
    }

        
    }
    
});
        // let in_use_rows = 0
        // cur_frm.doc.spare_item_tracking_detail.forEach(function(item_row){
        //     if (item_row.spare_status="In Use"){
        //         in_use_rows+=1
        //     }
        // })
        
        // if (cur_frm.doc.spare_item_tracking_detail.length==in_use_rows){
        // cur_frm.doc.spare_item_tracking_detail.forEach(function(item_row){
            
        // frappe.db.get_value('Item', frm.doc.spare_part, 'stock_uom').then(r => {
        //     if (!r.message) {
        //         frappe.msgprint("Item UOM not found");
        //         return;
        //     }

        // let item_uom = r.message.stock_uom;
        // let spare_part = frm.doc.spare_part;
        // let to_warehouse = frm.doc.spare_status === "Installation Pending" ?  frm.doc.target_warehouse : "";
        // let from_warehouse = frm.doc.spare_status === "Installation Pending" ? frm.doc.source_warehouse  : "";
        // let install_date = frm.doc.date_of_installation;
        // let stk_entry_type = frm.doc.spare_status === "Consumed" ? "Material Issue" :"Material Transfer"; 
        // let route = `/app/stock-entry/new-stock-entry-1?stock_entry_type=Material Transfer`;
        // // let spare_qty = frm.doc.spare_qty;

        
        // frappe.set_route("Form", "Stock Entry", "new-stock-entry-1");

        // setTimeout(() => {
        //     if (cur_frm && cur_frm.doc.doctype === "Stock Entry") {
        //         cur_frm.set_value("stock_entry_type", stk_entry_type);
        //         cur_frm.set_value("to_warehouse", to_warehouse);
        //         cur_frm.set_value("from_warehouse", from_warehouse);
        //         cur_frm.set_value("posting_date", install_date);
        //         cur_frm.set_value("set_posting_time", 1);
        //         cur_frm.set_value("custom_stock_entry_reference",frm.doc.doctype );
        //         cur_frm.clear_table("items");
                
        //         let child = cur_frm.add_child("items", {
        //             item_code: spare_part,
        //             qty: 1,
        //             transfer_qty : 1,
        //             uom: item_uom,
        //             stock_uom: item_uom,
        //             conversion_factor: 1,
        //             custom_stock_item_move_reference:frm.doc.name
        //             // t_warehouse: warehouse
        //         });
        //         cur_frm.refresh_field("items");
        //         cur_frm.refresh();
        //         cur_frm.save();
        //     }
            
        //     setTimeout(() => {let move_history_data = {
        //             spare_entry_reference: frm.doc.name,
        //             workstation: frm.doc.workstation,
        //             spare_part: frm.doc.spare_part,
        //             from_warehouse: frm.doc.source_warehouse,
        //             to_warehouse: frm.doc.target_warehouse,
        //             entry_date: install_date,
        //             current_status: frm.doc.spare_status,
        //             stock_entry_reference: cur_frm.doc.name,
        //             entry_details: `Initial installation recorded for spare item (${frm.doc.spare_part}). 
        //         Transferred from ${from_warehouse} to ${to_warehouse}. 
        //         Commissioned at workstation on ${install_date}.`
        //         };
        //     // console.log('here is the all filled data - ', move_history_data)
        //     frappe.call({
        //         method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.create_move_history",
        //         args: {
        //             data: move_history_data
        //         },
        //         // callback: function(r) {
        //         //             // console.log("Move history created: ", r.message);
        //         //     }
        //     })
        // },700);
            
        //     // console.log('here is the stock move history doc --',spare_move_his_doc)
        //     // console.log('move history doc name -- --',spare_move_his_doc.name)
        // }, 600);
        // });



//     if (frm.doc.docstatus==1){
    //         //  New task work ==============================//

    //     // Match record in Stock Entry Detail
    //     // let linked_stock_entry = frappe.db.get_list('Stock Entry Detail',{filters:{
    //     //             'custom_stock_item_move_reference':frm.doc.name,
    //     //         },fields:["name","parent"],limit:1}).then(linked_stock_entry=>{

    //     //             console.log('yeee le ',linked_stock_entry)
    //     //         })


    //     // console.log('here is the r -----')
    //     // frappe.call({
    //     //     method: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.find_linked_stock_entry',
    //     //     args:{
    //     //         'docname':frm.doc.name
    //     //     } ,
    //     //     callback:function(r){
    //     //         console.log('here is the r -----',r.message)
    //     //     }
    //     // });
        
    //     // /frappe.call({
    //     //     method: 'frappe.client.get_list',
    //     //     args:{
    //     //         doctype:"Stock Entry Detail",
    //     //         filters:{
    //     //             'custom_stock_item_move_reference':frm.doc.name,
    //     //         },
    //     //         fields:['name','parent'],
    //     //         // limit
    //     //     } ,
    //     //     callback:function(r){
    //     //         console.log('here is the r -----',r.message)
    //     //     }
    //     // });
    //     // frappe.db.call({
    //     //     method: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.workstation_spare_parts.workstation_spare_parts.find_linked_stock_entry',
    //     //     args:{
    //     //         docname:frm.doc.name,
    //     //         // limit
    //     //     } ,
    //     //     callback:function(r){
    //     //         console.log('here is the r -----',r.message)
    //     //     }
    //     // });

    //     // let linked_stock_entry = frappe.db.get_list('Stock Entry Detail',filters={

    //     // ================================  Old work start from here ==================================== //
    //     let in_use_rows = 0
    //     let maintenance_rows = 0
    //     let dispose_rows = 0
        



    //     let dispose_button = frm.fields_dict['spare_item_tracking_detail'].grid.add_custom_button('Dispose', function() {
    //     })

    //     let back_to_in_use_button = frm.fields_dict['spare_item_tracking_detail'].grid.add_custom_button('Back To In-use', function() {
            
    //     })
    //     let repair_button = frm.fields_dict['spare_item_tracking_detail'].grid.add_custom_button('Send to Repair', function() {
    //         let selected_rows_names = frm.fields_dict['spare_item_tracking_detail'].grid.get_selected();
    //         all_selected_docs = []
    //         today_date = frappe.datetime.get_today()
    //         selected_rows_names.forEach(function(selected_row) {
    //             all_selected_docs.push(frappe.get_doc("Spare Item Tracking Detail", selected_row))
    //         })
    //         const spare_table_data = all_selected_docs.map(row_doc => {
    //     return {
    //         source_warehouse: row_doc.source_warehouse,
    //         target_warehouse: row_doc.target_warehouse,
    //         spare_part  :   row_doc.spare_part,
    //         spare_qty   : row_doc.spare_qty,
    //         maintenance_start_date: today_date,
    //         line_id: row_doc.name
    //         // maintenance_responsible_party :
    //     };
    // })
    //         let d = new frappe.ui.Dialog({
    //                     title: 'Enter Detials For Repairing Spares',
    //                     size:'extra-large',
    //                     fields: [
    //                 {
	// 					label: 'Spares Details For Stock Entry',
	// 					fieldname: 'spares_details_for_stock_entry',
	// 					fieldtype: 'Table',
	// 					cannot_add_rows: false,
	// 					in_place_edit: false,
	// 					data:spare_table_data,
	// 					fields: [
	// 						{ label: 'Source Warehouse', fieldname: 'source_warehouse', fieldtype: 'Link',options:'Warehouse', in_list_view: 1 ,width:150, "reqd": 1  },
	// 						{ label: 'Target Warehouse', fieldname: 'target_warehouse', fieldtype: 'Link',options:'Warehouse', in_list_view: 1,"reqd": 1 },
	// 						{ label: 'Maintenance Start Date', fieldname: 'maintenance_start_date', fieldtype: 'Date', in_list_view: 1, "reqd": 1 },
	// 						{ label: 'Spare Part', fieldname: 'spare_part', fieldtype: 'Link',options:'Item', in_list_view: 1 ,read_only: true, "reqd": 1  },
	// 						{ label: 'Spare Qty', fieldname: 'spare_qty', fieldtype: 'Float', in_list_view: 1 ,width: '10%', "reqd": 1 },
	// 						{ label: 'Maintenance Responsible Party', fieldname: 'maintenance_responsible_party', fieldtype: 'Data', in_list_view: 1 },
	// 						{ label: 'Line Id', fieldname: 'line_id', fieldtype: 'Link',options:'Spare Item Tracking Detail', in_list_view: 1 },
	// 					]
	// 				},
    //                     ],
    //                     primary_action_label: 'Submit',
    //                     primary_action(values) {
    //                         // console.log(values);
    //                         // console.log('line id --',values.spares_details_for_stock_entry.line_id)
    //                         // console.log('spares_details_for_stock_entry------------',values.spares_details_for_stock_entry)
                            
    //                         all_selected_docs.forEach(function(doc_row){
    //                             values.spares_details_for_stock_entry.forEach(function(box_row){
    //                                 if (doc_row.name === box_row.line_id){
    //                                     if (doc_row.spare_qty > box_row.spare_qty){
    //                                         console.log('Have to make a new row under doc row')
    //                                         frappe.model.set_value('Spare Item Tracking Detail',doc_row.name,'spare_qty',doc_row.spare_qty - box_row.spare_qty )
    //                                         let child = cur_frm.add_child("spare_item_tracking_detail", doc_row );
    //                                         child.spare_qty = box_row.spare_qty
    //                                         // child.idx = doc_row.idx + 1
    //                                         child.spare_status = "Sent For Repair"
    //                                         child.maintenance_start_date = box_row.maintenance_start_date
    //                                         cur_frm.doc.spare_item_tracking_detail.splice(doc_row.idx, 0, child);
    //                                         cur_frm.doc.spare_item_tracking_detail.pop();
    //                                         cur_frm.doc.spare_item_tracking_detail.forEach((row, index) => {
    //                                             row.idx = index + 1;
    //                                         });
    //                                         cur_frm.refresh_field("spare_item_tracking_detail");
    //                                     }
    //                                 }
    //                             })
    //                         })
                            
    //                         d.hide();
    //                     }
    //                 });
    //         d.show();
    //         // dialog.fields_dict.dialog_table_fieldname.grid.refresh();
    //     });

    //     $(dispose_button).hide();
    //     $(back_to_in_use_button).hide();
    //     $(repair_button).hide();

    //     frm.fields_dict['spare_item_tracking_detail'].grid.wrapper.on('change', '.grid-row-check', function() {
    //         // alert('yeeeey')
    //         setTimeout(function() {
            
    //             // let selected_rows = frm.fields_dict['spare_item_tracking_detail'].grid.get_selected();
    //     let selected = frm.fields_dict['spare_item_tracking_detail'].grid.get_selected();
    //     // console.log('---here iss the selefted --',selected)
    //     if (selected.length > 0) {
    //         let row_count = 0;
    //         let already_selected_rows = []
    //         selected.forEach(function(selected_row) {
    //             // console.log('thsi hte for loop row data -selecteddd--',selected)
    //             // console.log('thsi sihte for loop row data -selecteddd rowwww--',selected_row)
    //             if (!already_selected_rows.includes(selected_row)){
    //                 already_selected_rows.push(selected_row)
    //                 // console.log('this is the already selected rows --',already_selected_rows)
    //             let row_data = frappe.get_doc("Spare Item Tracking Detail", selected_row);
    //             // console.log('this is for loop row data -rowdata variable  rowwww--',row_data)
                
    //                 if(row_data.spare_status==="In Use"){
    //                     in_use_rows += 1
    //                 }

    //                 if(row_data.spare_status==="Sent For Repair"){
    //                     maintenance_rows += 1
    //                 }

    //                 if(row_data.spare_status==="Consumed"){
    //                     dispose_rows += 1
    //                 }
    //             }
    //         });

    //         if (in_use_rows == selected.length) {
    //                         // console.log('---------------------in_use_rows----',in_use_rows)
    //                         $(dispose_button).show(selected);
    //                         $(repair_button).show(selected);
    //                         in_use_rows = 0
    //                 maintenance_rows = 0
    //                 dispose_rows = 0
    //                     }
    //         else if (maintenance_rows == selected.length) {
    //                 $(dispose_button).show();
    //                 $(back_to_in_use_button).show();
    //                 in_use_rows = 0
    //                 maintenance_rows = 0
    //                 dispose_rows = 0
    //             }
    //         else {
    //                 // in_use_rows = 0
    //                 // maintenance_rows = 0
    //                 // dispose_rows = 0
    //                 $(dispose_button).hide();
    //                 $(back_to_in_use_button).hide();
    //                 $(repair_button).hide();
    //                 in_use_rows = 0
    //                 maintenance_rows = 0
    //                 dispose_rows = 0
    //             }
    //         // console.log('---------------------in_use_rows----',in_use_rows)
    //         }
    //             // if (selected.length > 0 && maintenance_rows == selected.length) {
    //             //     $(dispose_button).show();
    //             //     $(back_to_in_use_button).show();
    //             // } 
    //             else {
    //                 in_use_rows = 0
    //                 maintenance_rows = 0
    //                 dispose_rows = 0
    //                 $(dispose_button).hide();
    //                 $(back_to_in_use_button).hide();
    //                 $(repair_button).hide();
    //             }
    //         }, 50);
    //     });}
    //     // frm.fields_dict["spare_item_tracking_detail"].grid.add_custom_button(__('Hello'),
    //     // function(){
    //     //     frappe.msgprint(__("Hello"));
    //     // })
    //     // frm.fields_dict["spare_item_tracking_detail"].grid.grid_buttons.find('.btn-custom').removeClass('btn-default').addClass('btn-primary');
    // },
    // spare_status(frm) {
    //     // if (!frm.doc.spare_part || !frm.doc.target_warehouse) {
    //     //     frappe.msgprint("Please select Spare Part and Workstation Warehouse before changing spare_status.");
    //     //     return;
    //     // }
        
    //     // frm.set_query('source_warehouse',function(){
    //     //     if (frm.doc.spare_status==='In Use'){
    //     //             return{
    //     //             'parent_warehouse' : ['like',['Racks','maintenance']]
    //     //             }
    //     //         }

    //     //     else if (frm.doc.spare_status==='Consumed'){
    //     //             return{
    //     //             'parent_warehouse' : ['like',['Workstations Spares','maintenance']]
    //     //             }

    //     //     }
    //     // })

    //     // Fetch UOM first (used in all transitions)
    //     frappe.db.get_value("Item", frm.doc.spare_part, "stock_uom").then(r => {
    //         if (!r.message) {
    //             frappe.msgprint("Item UOM not found.");
    //             return;
    //         }

    //         let item_uom = r.message.stock_uom;
    //         let spare_part = frm.doc.spare_part;
    //         let from_wh = frm.doc.source_warehouse || "";
    //         let to_wh = frm.doc.target_warehouse || ""; 
    //         let install_date = frm.doc.date_of_installation;
    //         let todayDate = frappe.datetime.get_today();
    //         let spare_qty = frm.doc.spare_qty;
    //         // console.log("-------------eeee",todayDate)

    //         // -------- CASE 1: In Use → Sent For Repair --------
    //         if (frm.doc.docstatus === 1 && frm.doc.spare_status === "Sent For Repair") {
    //             frappe.confirm(
    //                 `A Stock Entry will be created for <b>${spare_part}</b>.<br>
    //                 Please set <b>Target Warehouse</b> to the Maintenance location.<br><br>
    //                 Continue to create Stock Entry?`,
    //                 () => {
    //                     frm.save('Update').then(() => {
    //                         create_stock_entry(
    //                             "Material Transfer",
    //                             from_wh,
    //                             to_wh,
    //                             spare_part,
    //                             item_uom,
    //                             frm.doc.name,
    //                             todayDate,
    //                             "Transferred from workstation to maintenance.",
    //                             spare_qty
    //                         );
    //                     });
    //                 }
    //             );
    //         }

    //         // -------- CASE 2: Sent For Repair → In Use --------
    //         else if (frm.doc.docstatus === 1 && frm.doc.spare_status === "In Use") {
    //             frappe.confirm(
    //                 `The spare part <b>${spare_part}</b> is now being set to <b>In Use</b>.<br>
    //                 Do you want to create a Stock Entry to move it back to the workstation warehouse?`,
    //                 () => {
    //                     frm.save('Update').then(() => {
    //                         setTimeout(() => {
    //                         create_stock_entry(
    //                             "Material Transfer",
    //                             from_wh,
    //                             to_wh,
    //                             spare_part,
    //                             item_uom,
    //                             frm.doc.name,
    //                             todayDate,
    //                             "Returned from maintenance to workstation.",
    //                             spare_qty
    //                         );
    //                         }, 500);

    //                     });
    //                 }
    //             );
    //         }

    //         // -------------- case 3: Sent For Repair → Consumed ---  ----  -
            
    //     });
    // },




    // // dispose_replacement_date
    // // spare_status: function (frm) {

    // //     if (frm.doc.spare_status != "Consumed" && frm.doc.dispose_replacement_date) {
    // //         frm.set_value("dispose_replacement_date", false);
    // //     }

    // // },

    
    // dispose_replacement_date: function (frm) {
    //     if (frm.doc.dispose_replacement_date && frm.doc.date_of_installation) {
    //         if (frm.doc.date_of_installation > frm.doc.dispose_replacement_date) {
    //             frappe.msgprint({
    //                 title: __("Invalid Date Selection"),
    //                 message: __("The Dispose/Replacement Date must be after the Date of Installation."),
    //                 indicator: "red"
    //             });
    //             frm.set_value("dispose_replacement_date", "");
    //             return;
    //         }

    //         let install = frappe.datetime.str_to_obj(frm.doc.date_of_installation);
    //         let dispose = frappe.datetime.str_to_obj(frm.doc.dispose_replacement_date);
    //         let diff_days = frappe.datetime.get_day_diff(dispose, install);
    //         frm.set_value("service_life_days", diff_days);

    //     frappe.db.get_value("Item", frm.doc.spare_part, "stock_uom").then(r => {
    //         if (!r.message) {
    //             frappe.msgprint("Item UOM not found.");
    //             return;
    //         }

    //         let item_uom = r.message.stock_uom;
    //         let spare_part = frm.doc.spare_part;
    //         let from_wh = frm.doc.source_warehouse || "";
    //         let to_wh = frm.doc.target_warehouse || ""; 
    //         // let install_date = frm.doc.date_of_installation;
    //         // let todayDate = frappe.datetime.get_today();
    //         let spare_qty = frm.doc.spare_qty;
    //         let dispose_date = frm.doc.dispose_replacement_date;

    //         // let previous_status = frm.doc.__unsaved ? frm.doc._previous_status : frm.docstatus_before_dispose;


    //         if (frm.doc.docstatus === 1 && frm.doc.spare_status === "Consumed") {
    //                 frappe.confirm(
    //                     `This part <b>${spare_part}</b> will be <b>Consumed</b>.<br>
    //                     A Material Issue entry will be created and it cannot be reverted.<br><br>
    //                     Proceed to Dispose?`,
    //                     () => {
    //                         frm.save('Update').then(() => {
    //                             setTimeout(() => {
    //                                 create_stock_entry(
    //                                     "Material Issue",
    //                                     from_wh,
    //                                     to_wh,
    //                                     spare_part,
    //                                     item_uom,
    //                                     frm.doc.name,
    //                                     dispose_date,
    //                                     "Consumed permanently from maintenance stock.",
    //                                     spare_qty
    //                             );
    //                             }, 500);
    
    //                             // Optional: disable editing after disposal
    //                             frappe.after_ajax(() => {
    //                                 frm.set_df_property("spare_status", "read_only", 1);
    //                                 frm.set_df_property("spare_part", "read_only", 1);
    //                                 frappe.msgprint("Spare part has been Consumed. Further changes are locked.");
    //                             });
    //                         });
    //                     },
    //                     // (){
    //                     //     frappe.msgprint('Action Cancelled, Refreshing....')

    //                     // }
    //                 );
    //             }
    //     });

    //     }

    //     if (frm.doc.dispose_replacement_date && frm.doc.spare_status !== "Consumed") {
    //         frm.set_value("spare_status", "Consumed");
    //     }
    //     // ================================  Old work end here ==================================== //

    // refresh:
    