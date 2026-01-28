frappe.ui.form.on("Sales Order", {
    onload_post_render: function (frm) {
        if (!frm.doc.delivery_date && frm.doc.transaction_date) {
            frm.set_value(
                "delivery_date",
                frappe.datetime.add_days(frm.doc.transaction_date, 45)
            );
        }
    },

    refresh: function (frm) {
        // Add Release Order button when SO is submitted
        if (frm.doc.docstatus === 1) {
            // Check if there are pending items
            let has_pending = false;
            if (frm.doc.items) {
                for (let item of frm.doc.items) {
                    if (flt(item.qty) > flt(item.delivered_qty)) {
                        has_pending = true;
                        break;
                    }
                }
            }

            if (has_pending) {
                frm.add_custom_button(
                    __("Release Order"),
                    function () {
                        frappe.model.open_mapped_doc({
                            method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.release_order.release_order.make_release_order",
                            frm: frm,
                        });
                    },
                    __("Create")
                );
            }
        }

        // Show linked Release Orders in dashboard
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(
                __("View Release Orders"),
                function () {
                    frappe.set_route("List", "Release Order", {
                        sales_order: frm.doc.name,
                    });
                },
                __("View")
            );
        }
    },
})