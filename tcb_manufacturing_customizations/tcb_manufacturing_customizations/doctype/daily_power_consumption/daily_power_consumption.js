frappe.ui.form.on('Daily Power Consumption', {

    onload: function (frm) {

    
        if (!frm.doc.date) {
            frm.set_value(
                'date',
                frappe.datetime.add_days(
                    frappe.datetime.get_today(), -1
                )
            );
        }

     
        if (frm.is_new() && frm.doc.power_details.length === 0) {

            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Workstation",
                    fields: ["name"],
                    limit_page_length: 1000
                },
                callback: function (r) {

                    if (r.message) {
                        r.message.forEach(function (ws) {
                            let row = frm.add_child("power_details");
                            row.machine = ws.name;
                        });

                        frm.refresh_field("power_details");
                    }
                }
            });
        }
    }
});

frappe.ui.form.on('Daily Power Consumption', {

    onload(frm) {

      
        if (!frm.doc.date) {
            frm.set_value(
                'date',
                frappe.datetime.add_days(
                    frappe.datetime.get_today(), -1
                )
            );
        }

        
        if (frm.is_new() && frm.doc.power_details.length === 0) {

            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Workstation",
                    fields: ["name"],
                    limit_page_length: 1000
                },
                callback(r) {
                    if (r.message) {
                        r.message.forEach(ws => {
                            let row = frm.add_child("power_details");
                            row.machine = ws.name;
                        });
                        frm.refresh_field("power_details");
                    }
                }
            });
        }
    }
});


frappe.ui.form.on('Daily Power Consumption Table', {

    power_consumption(frm, cdt, cdn) {

        let total = 0;

        frm.doc.power_details.forEach(row => {
            total += row.power_consumption || 0;
        });

        frm.set_value('total_power', total);
    }
});

