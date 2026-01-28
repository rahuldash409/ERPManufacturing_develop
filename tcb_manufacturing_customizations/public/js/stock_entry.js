frappe.ui.form.on("Stock Entry",{
    
    // onload: function(frm) {
    //     setup_serial_filter(frm);
    //     alert('=====onload===============')
    // },
    // refresh: function(frm) {
    //     setup_serial_filter(frm);
    //     alert('=====refresh===============')

    // }
// validate :async function(frm){
    // if (frm.doc.stock_entry_type === "Spares Transfer"){
    // await frappe.call({
    // method:'tcb_manufacturing_customizations.doc_events.stock_entry.seperate_repairable_spares_quantities',
    // args: {
    //     docname: frm.doc.name,
    //     },
    //     callback:(r)=>{
    //     console.log('ehrerooooooooooooooo')
    //     frm.refresh_field("items");

    // }
    // });

    // }
    // }

    // onload:function(frm){
    //     if(frm.doc.docstatus==1 && frm.doc.stock_entry_type=="Manufacture"){
    //         frappe.call({
    //             method:"tcb_manufacturing_customizations.doc_events.stock_entry.update_batches",
    //             args:{
    //                 docname:frm.doc.name
    //             },
    //             callback:(r)=>{
    //                 if(!r.exc){
    //                 }
    //             }
    //         })
    //     }
        // if(frm.doc.docstatus==1 && frm.doc.stock_entry_type =="Material Transfer for Manufacture"){
        //     frappe.call({
        //         method:"tcb_manufacturing_customizations.doc_events.stock_entry.set_sub_batch",
        //         args:{
        //             docname:frm.doc.name
        //         },
        //         callback:(r)=>{
        //             if(!r.exc){
        //                 // frm.reload_doc()
        //             }
        //         }
        //     })
        // }
    
// }
})
frappe.ui.form.on("Stock Entry", {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn]

        frm.fields_dict["items"].grid.get_field("custom_select_serial_no").get_query = function (doc,cdt,cdn) {
			return {
				filters: {
					"item_code":row.item_code,
                    "warehouse":row.s_warehouse
				},
			};
		};




        // setup_serial_filter(frm);
        // // Clear existing serial number
        // frappe.model.set_value(cdt, cdn, 'custom_select_serial_no', '');
    },
    
    items_add: function(frm, cdt, cdn) {
        if (frm.doc.custom_default_workstation) {
            frappe.model.set_value(cdt, cdn, "custom_workstation", frm.doc.custom_default_workstation);
        }
    }
});

// function setup_serial_filter(frm) {
//     frm.set_query("custom_select_serial_no", "items", function(doc, cdt, cdn) {
//         let row = locals[cdt][cdn];
//         if (row && row.item_code) {
//             return {
//                 filters: {
//                     'item_code': row.item_code,
//                     'status': 'Active'
//                 }
//             };
//         }
//         return {};
//     });
// }