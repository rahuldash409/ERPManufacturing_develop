frappe.ui.form.on("Purchase Receipt", {

    onload: function (frm) {
        hide_items_upload_button(frm);

        if(frm.get_field("set_warehouse").value==undefined || frm.get_field("set_warehouse").value==""){
            frm.set_value("set_warehouse","Raw Material - APUI" )
        }
    },

    refresh: function (frm) {
        hide_items_upload_button(frm);

        // if (frm.doc.docstatus == 0 && frm.doc.custom_import_sap_file && !frm.is_new()) {
        //     frm.add_custom_button(__('Import SAP Items'), function () {
        //         process_sap_import(frm);
        //     }).css({ 'background-color': '#28a745', 'color': 'white' });
        // }

        if (frm.doc.docstatus == 1) {
            frappe.call({
                method: "tcb_manufacturing_customizations.doc_events.purchase_receipt.update_batches",
                args: {
                    docname: frm.doc.name
                }
            });
            frappe.call({
                method: "tcb_manufacturing_customizations.doc_events.purchase_receipt.set_container_data",
                args: {
                    docname: frm.doc.name
                }
            });
        }

        // Thi is an old function that was used to trigger bales creation from purchase receipt. Now not needed.. Need confirmation for deletion
        // if(frm.doc.docstatus==1 && !frm.doc.custom_bales_created){
        //     frappe.call({
        //         method:"tcb_manufacturing_customizations.doc_events.bales.trigger_bales_from_purchase",
        //         args:{
        //             docname:frm.doc.name
        //         }
        //     })
        // }
        // setTimeout(()=>{
        //     frm.refresh_field("custom_bales_created")
        // },1000)
    },

    onload_post_render: function (frm) {
        hide_items_upload_button(frm);

        // if (frm.doc.docstatus == 0 && frm.doc.set_warehouse && !frm.is_new()) {
        //     frappe.call({
        //         method: "tcb_manufacturing_customizations.doc_events.purchase_receipt.qc_check",
        //         args: {
        //             docname: frm.doc.name
        //         },
        //         callback: (r) => {
        //             frm.refresh_field("items");
        //         }
        //     });
        // }
    },


    custom_import_sap_file:function(frm){
        try{
            process_sap_import(frm)
        }
        catch(e){
            console.log("error occured during uploading sap fiel -",e)
        }
    }
});

function hide_items_upload_button(frm) {
    setTimeout(function () { remove_items_upload(frm); }, 100);
    setTimeout(function () { remove_items_upload(frm); }, 300);
    setTimeout(function () { remove_items_upload(frm); }, 500);
    setTimeout(function () { remove_items_upload(frm); }, 1000);
}

function remove_items_upload(frm) {
    if (frm.fields_dict.items && frm.fields_dict.items.grid) {

        // if (!$('#hide-pr-items-upload').length) {
        //     $('head').append(`
        //         <style id="hide-pr-items-upload">
        //             /* Hide Upload button ONLY in Purchase Receipt Items table */
        //             [data-doctype="Purchase Receipt"] [data-fieldname="items"] .grid-upload-button,
        //             [data-doctype="Purchase Receipt"] [data-fieldname="items"] button:contains("Upload") {
        //                 display: none !important;
        //                 visibility: hidden !important;
        //             }
        //         </style>
        //     `);
        // }

        frm.fields_dict.items.grid.wrapper.find('.grid-upload-button').remove();
        frm.fields_dict.items.grid.wrapper.find('button:contains("Upload")').each(function () {
            if ($(this).text().trim() === 'Upload') {
                $(this).remove();
            }
        });

        // frm.fields_dict.items.$wrapper.find('.grid-buttons button').each(function () {
        //     if ($(this).text().trim() === 'Upload') {
        //         $(this).remove();
        //     }
        // });
    }


}




function process_sap_import(frm) {
    // if (!frm.doc.name) {
    //     frappe.msgprint({
    //         title: __('Error'),
    //         indicator: 'red',
    //         message: __('Document must be saved first.')
    //     });
    //     return;
    // }

    if (!frm.doc.custom_import_sap_file) {
        frappe.msgprint({
            title: __('No File'),
            indicator: 'orange',
            message: __('Please upload an SAP file first.')
        });
        return;
    }

    frappe.show_alert({
        message: __('Importing SAP data...'),
        indicator: 'blue'
    });

    let supp = frm.get_field("supplier").value

    if(!supp){
        frappe.throw("Please Set a Supplier")
    }

    if(supp){
        frappe.call({
            method: 'tcb_manufacturing_customizations.doc_events.purchase_receipt.import_sap_to_purchase_receipt',
            args: {
                // purchase_receipt_name: frm.doc.name,
                file_url: frm.get_field("custom_import_sap_file").value,
                supplier_Val: frm.get_field("supplier").value,
                purchase_order: frm.get_field("custom_purchase_order").value
            },
            freeze: true,
            freeze_message: __('Processing SAP file...'),
            callback: function (r) {
                if (r.message && r.message.status === 'success') {
                    if (r.message.items_data && r.message.items_data.length > 0) {
                        frm.clear_table("items")
                        r.message.items_data.forEach(function (item_data) {
                            frm.add_child("items", item_data);
                        });
                    }

                    frm.refresh_field("items");
                    frm.dirty();

                    frappe.show_alert({
                        message: r.message.message,
                        indicator: 'green'
                    }, 7);

                    frappe.msgprint({
                        title: __('Success'),
                        indicator: 'green',
                        message: __('Imported {0} items successfully. Please Save.', [r.message.items_count])
                    });
                }
            },
            error: function (r) {
                frappe.msgprint({
                    title: __('Import Failed'),
                    indicator: 'red',
                    message: __('Failed to import SAP file.')
                });
            }
        });
    }
}
