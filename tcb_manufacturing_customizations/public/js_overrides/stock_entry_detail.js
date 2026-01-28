frappe.ui.form.on("Stock Entry Detail", {
    // frm.fields_dict.items.grid.toggle_display("t_warehouse", 0)

    item_code: function(frm, cdt, cdn) {
        frm.set_query("custom_select_serial_no", "items", function(doc, cdt, cdn) {
            
        let row = locals[cdt][cdn];
        if (row && row.item_code && row.qty == 1 && doc.stock_entry_type =="Spares Transfer") {
            return {
                filters: {
                    'item_code': row.item_code,
                    "warehouse":row.s_warehouse,
                    'status': 'Active'
                }
            };
        }
        else {
            return {
                filters: {
                    'item_code': '',
                    // 'status': 'Active'
                }
            };
        }
    });
        frappe.model.set_value(cdt, cdn, 'custom_select_serial_no', '');
        frm.refresh_field('items');
    },

    custom_select_serial_no: function(frm, cdt, cdn){
    let row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, 'serial_no', row.custom_select_serial_no);
        //  Fetch the spare doc linked to this serial no and set the name of that spare doc in the custom_stock_item_move_reference field
        frappe.db.get_value('Workstation Spare Parts', {'item_serial_number': row.custom_select_serial_no, 'spare_part': row.item_code}, 'name').then(r => {
            if (r && r.message) {
                frappe.model.set_value(cdt, cdn, 'custom_stock_item_move_reference', r.message.name);
            }
            if (!r.message) {
                frappe.throw(`No Workstation Spare Parts document found for Serial No: ${row.custom_select_serial_no} and Item Code: ${row.item_code}`);
            }
        });
    },
    items_add(frm, cdt, cdn) {
        if (frm.doc.custom_default_workstation)
            // console.log('here is the ====',frm.doc.custom_default_workstation)
            frappe.model.set_value(cdt, cdn, "custom_workstation", frm.doc.custom_default_workstation);
    }
});