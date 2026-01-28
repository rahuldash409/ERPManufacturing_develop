frappe.ui.form.on("Get All Batch Qty", {
    calculate_all_batch_qty: function(frm) {
        if (!frm.doc.item) {
            frappe.msgprint("Please select an Item first.");
            return;
        }

        let sum = 0;

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Batch",
                filters: {
                    item: frm.doc.item,
                    batch_qty: [">", 0]
                },
                fields: ["custom_segregated_item_qty"],
                limit_page_length: 0
            },
            callback: function(r) {

                if (r.message) {
                    r.message.forEach(row => {
                        sum += row.custom_segregated_item_qty || 0;
                    });
                }

                frm.set_value("all_batch_qty", sum);
                frm.refresh_field("all_batch_qty");

            }
        });
    }
});