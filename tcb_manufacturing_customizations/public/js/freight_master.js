frappe.ui.form.on("Freight Master", {
    refresh: function(frm) {
        frm.set_query("port", function() {
            return {
                filters: {
                    delivery_type: frm.doc.delivery_type || ""
                }
            };
        });
    },

    delivery_type: function(frm) {
        frm.set_query("port", function() {
            return {
                filters: {
                    delivery_type: frm.doc.delivery_type || ""
                }
            };
        });
    }
});
