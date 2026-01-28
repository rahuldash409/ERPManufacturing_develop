frappe.ui.form.on('Production Plan', {
    refresh: function(frm) {
        // Add refresh button only after submit to check if materials received
        // if (frm.doc.docstatus === 1 && frm.doc.mr_items && frm.doc.mr_items.length > 0) {
        //     frm.add_custom_button(__('🔄 Refresh Material Status'), function() {
        //         frm.trigger('refresh_material_status');
        //     }).css({'background-color': '#17a2b8', 'color': 'white', 'font-weight': 'bold'});
        // }

        // Show material status indicator
        if (frm.doc.mr_items && frm.doc.mr_items.length > 0) {
            frm.trigger('show_material_status');
        }
    },

    // Hook into standard "Get Items For MR" button
    get_items_for_mr: function(frm) {
        return
        frm.save()
        // Wait for standard process to complete
        setTimeout(() => {
            if (frm.doc.docstatus === 0) {
                frm.trigger('add_baling_to_mr_items');
                frm.doc.mr_items.forEach((item)=>{
                    item.quantity = Math.ceil(item.quantity)
                })
            }
        }, 1000);
    },

    add_baling_to_mr_items: function(frm) {
        return
        frappe.call({
            method: "tcb_manufacturing_customizations.doc_events.production_plan.add_baling_to_mr_items",
            args: {
                production_plan_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message) {
                    let data = r.message;

                    // Clear existing baling materials
                    frm.clear_table('custom_baling_materials');

                    // Add baling materials to custom_baling_materials table
                    data.baling_materials.forEach(item => {
                        frm.add_child('custom_baling_materials', item);
                    });

                    // Add shortage items to mr_items table
                    data.items_to_add.forEach(item => {
                        // Check if item already exists
                        let existing = frm.doc.mr_items.find(row => row.item_code === item.item_code);
                        if (existing) {
                            existing.quantity += item.quantity;
                        } else {
                            frm.add_child('mr_items', item);
                        }
                    });

                    // Refresh fields
                    frm.refresh_field('custom_baling_materials');
                    frm.refresh_field('mr_items');

                    if (data.items_to_add.length > 0) {
                        frappe.show_alert({
                            message: __('Added {0} baling materials', [data.items_to_add.length]),
                            indicator: 'green'
                        });
                    }
                }
            }
        });
    },

    show_material_status: function(frm) {
        frappe.call({
            method: "tcb_manufacturing_customizations.doc_events.production_plan.check_mr_items_stock",
            args: {
                production_plan_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message) {
                    if (r.message.has_shortage) {
                        // frm.dashboard.add_indicator(
                    //         __('Bales Material Shortage: {0} items', [r.message.shortage_count]),
                    //         'red'
                    //     );
                    // } else {
                    //     frm.dashboard.add_indicator(
                    //         __('All Bales Materials Available'),
                    //         'green'
                        // );
                    }
                }
            }
        });
    }
});
