// Copyright (c) 2025, TCB Infotechpvtltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Release Order", {
    refresh: function (frm) {
        // Update delivered_qty from Sales Order for submitted Release Orders
        if (frm.doc.docstatus === 1 && frm.doc.sales_order && frm.doc.items) {
            frm.trigger("update_delivered_qty_from_so");
        }

        // Add Create Delivery Note button when submitted
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(
                __("Delivery Note"),
                function () {
                    frappe.model.open_mapped_doc({
                        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.release_order.release_order.make_delivery_note",
                        frm: frm,
                    });
                },
                __("Create")
            );
        }

        // Add helper buttons in draft mode
        if (frm.doc.docstatus === 0 && frm.doc.items && frm.doc.items.length > 0) {
            frm.add_custom_button(__("Set All to Pending"), function () {
                frm.doc.items.forEach((item) => {
                    frappe.model.set_value(
                        item.doctype,
                        item.name,
                        "release_qty",
                        item.pending_qty
                    );
                });
                frm.refresh_field("items");
                frm.trigger("calculate_totals");
            });

            frm.add_custom_button(__("Clear All Qty"), function () {
                frm.doc.items.forEach((item) => {
                    frappe.model.set_value(
                        item.doctype,
                        item.name,
                        "release_qty",
                        0
                    );
                });
                frm.refresh_field("items");
                frm.trigger("calculate_totals");
            });
        }
        


        // Add a filter to the address name
        frm.set_query("shipping_address_name",function(){
            return{
                filters:{
                    link_name:frm.get_field("customer").value
                }
            }
        })
        frm.set_query("customer_address",function(){
            return{
                filters:{
                    link_name:frm.get_field("customer").value
                }
            }
        })
    },


    // SET SHIPPING ADDRESS
    shipping_address_name:async function(frm){
        try{
            let address = ""
            let add_doc = await frappe.db.get_doc("Address",frm.get_field("shipping_address_name").value)

            address+=`${add_doc.address_line1 || ""} \n${add_doc.address_line2 || ""} \n${add_doc.city || ""} \n${add_doc.state || ""}, ${add_doc.country || ""} \n${add_doc.pincode || ""}`
            frm.set_value("shipping_address",address)
        }
        catch{

        }
        
    },
    customer_address:async function(frm){
        try{
            let address = ""
            let add_doc = await frappe.db.get_doc("Address",frm.get_field("customer_address").value)

            address+=`${add_doc.address_line1 || ""} \n${add_doc.address_line2 || ""} \n${add_doc.city || ""} \n${add_doc.state || ""}, ${add_doc.country || ""} \n${add_doc.pincode || ""}`
            frm.set_value("address_display",address)
        }
        catch{

        }
        
    },

    sales_order: function (frm) {
        if (frm.doc.sales_order) {
            frm.trigger("fetch_sales_order_items");
        } else {
            // Clear items if SO is cleared
            frm.clear_table("items");
            frm.refresh_field("items");
        }
    },

    fetch_sales_order_items: function (frm) {
        frappe.call({
            method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.release_order.release_order.get_sales_order_items",
            args: {
                sales_order: frm.doc.sales_order,
            },
            callback: function (r) {
                if (r.message && r.message.length > 0) {
                    frm.clear_table("items");

                    r.message.forEach((item) => {
                        let row = frm.add_child("items");
                        row.item_code = item.item_code;
                        row.item_name = item.item_name;
                        row.uom = item.uom;
                        row.warehouse = item.warehouse;
                        row.so_detail = item.so_detail;
                        row.so_qty = item.so_qty;
                        row.delivered_qty = item.delivered_qty;
                        row.pending_qty = item.pending_qty;
                        row.release_qty = item.release_qty;
                    });

                    frm.refresh_field("items");
                    frm.trigger("calculate_totals");
                } else {
                    frappe.msgprint({
                        title: __("No Pending Items"),
                        message: __(
                            "All items in this Sales Order have been fully delivered."
                        ),
                        indicator: "orange",
                    });
                    frm.set_value("sales_order", "");
                }
            },
        });
    },

    calculate_totals: function (frm) {
        let total = 0;
        if (frm.doc.items) {
            frm.doc.items.forEach((item) => {
                total += flt(item.release_qty);
            });
        }
        frm.set_value("total_qty", total);
    },

    update_delivered_qty_from_so: function (frm) {
        // Fetch latest delivered_qty from Sales Order items
        frappe.call({
            method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.release_order.release_order.get_so_items_delivery_status",
            args: {
                sales_order: frm.doc.sales_order,
            },
            callback: function (r) {
                if (r.message) {
                    let so_item_map = r.message;

                    // Update each RO item's delivered_qty and pending_qty display
                    let updated = false;
                    frm.doc.items.forEach((item) => {
                        if (item.so_detail && so_item_map[item.so_detail]) {
                            let so_data = so_item_map[item.so_detail];
                            if (item.delivered_qty !== so_data.delivered_qty) {
                                item.delivered_qty = so_data.delivered_qty;
                                item.pending_qty = so_data.pending_qty;
                                updated = true;
                            }
                        }
                    });

                    if (updated) {
                        frm.refresh_field("items");
                    }
                }
            },
        });
    },
});

frappe.ui.form.on("Release Order Item", {
    release_qty: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Validate release_qty
        if (flt(row.release_qty) > flt(row.pending_qty)) {
            frappe.msgprint({
                title: __("Warning"),
                message: __(
                    "Release Qty ({0}) exceeds Pending Qty ({1}) for item {2}",
                    [row.release_qty, row.pending_qty, row.item_code]
                ),
                indicator: "orange",
            });
        }

        if (flt(row.release_qty) < 0) {
            frappe.model.set_value(cdt, cdn, "release_qty", 0);
        }

        frm.trigger("calculate_totals");
    },

    items_remove: function (frm) {
        frm.trigger("calculate_totals");
    },
});
