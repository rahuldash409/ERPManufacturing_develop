// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bales Master", {
	setup(frm) {
		// Fetch default warehouse from TCB Settings
		frappe.db.get_single_value("TCB Settings", "default_bales_warehouse").then((default_warehouse) => {
			frm.set_value("warehouse", default_warehouse)
		});
	},

	refresh(frm) {
		if (frm.is_new() && !frm.doc.warehouse && frm.default_bales_warehouse) {
			frm.set_value("warehouse", frm.default_bales_warehouse);
		}
	},

	warehouse(frm) {
		// Update warehouse in all child rows when parent warehouse changes
		if (frm.doc.warehouse && frm.doc.items && frm.doc.items.length > 0) {
			frm.doc.items.forEach((row) => {
				frappe.model.set_value(row.doctype, row.name, "warehouse", frm.doc.warehouse);
			});
		}
	},

	auto_fetch_batch_data(frm, cdt, cdn){
		return
		let child = locals[cdt][cdn];
		let item_code = getAttr(child, "item_code", "")
		let warehouse = getAttr(child, "warehouse", "")
		let qty = getAttr(child, "qty", 0)
		if(item_code && warehouse && qty > 0){
			frappe.call({
				method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.bales_master.bales_master.auto_fetch_batch_data",
				args: {
					item_code: item_code,
					warehouse: warehouse,
					qty: qty,
				},
				callback(resp){
					console.log(resp)
					let message = resp.message;
					if(message.success){
						let data = message.data;
						if((data.batch_no != child.batch) || (data.sub_batch != child.sub_batch)){
							frappe.model.set_value(cdt, cdn, "batch", data.batch_no)
							frappe.model.set_value(cdt, cdn, "sub_batch", data.sub_batch)
							frappe.show_alert({
								message: __(message.msg),
								indicator: 'green'
							});
						}
					}
					else{
						frappe.model.set_value(cdt, cdn, "batch", "")
						frappe.model.set_value(cdt, cdn, "sub_batch", "")
					}
				}
			})
		} else {
			frappe.model.set_value(cdt, cdn, "batch", "")
			frappe.model.set_value(cdt, cdn, "sub_batch", "")
		}
	}
});

frappe.ui.form.on("Bales Master Item", {
    items_add(frm, cdt, cdn) {
        let item_code = getAttr(frm.doc, "item_code", null);
        if(item_code){
            frappe.model.set_value(cdt, cdn, "item_code", item_code);
        }
        // Set warehouse from parent
        if(frm.doc.warehouse){
            frappe.model.set_value(cdt, cdn, "warehouse", frm.doc.warehouse);
        }
    },
    item_code(frm, cdt, cdn) {
        let item_code = getAttr(frm.doc, "item_code", null);
        if(item_code){
            frappe.model.set_value(cdt, cdn, "item_code", item_code)
        }
		frm.events.auto_fetch_batch_data(frm, cdt, cdn)
	},
    warehouse(frm, cdt, cdn) {
		frm.events.auto_fetch_batch_data(frm, cdt, cdn)
	},
    qty(frm, cdt, cdn) {
		frm.events.auto_fetch_batch_data(frm, cdt, cdn)
	},

	create_bale(frm, cdt, cdn) {
		let child = locals[cdt][cdn];

		// Check if bales_id already exists
		if (child.bales_id) {
			frappe.msgprint(__("Bales already created for this row"));
			return;
		}

		let item_code = getAttr(child, "item_code", "");
		let warehouse = getAttr(child, "warehouse", "");
		let qty = getAttr(child, "qty", 0);
		let bales_source = getAttr(child, "bales_source", "");

		if (!item_code || !warehouse || !qty) {
			frappe.msgprint(__("Item Code, Warehouse and Qty are required"));
			return;
		}

		frappe.call({
			method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.bales_master.bales_master.create_bales",
			args: {
				item_code: item_code,
				warehouse: warehouse,
				qty: qty,
				bales_source: bales_source
			},
			callback(resp) {
				let message = resp.message;
				if (message.success) {
					frappe.model.set_value(cdt, cdn, "bales_id", message.bales_id);
					frm.save();
					frappe.show_alert({
						message: __(message.msg),
						indicator: 'green'
					});
				} else {
					frappe.msgprint(__(message.msg));
				}
			}
		});
	},
});



// Utils Start
function cleanValue(variable, default_value) {
	return variable
		? variable
		: default_value || isNaN(variable)
			? default_value
			: variable;
}

function getAttr(obj, key, default_value = null) {
	key = key.trim();
	try {
		return cleanValue(obj[key], default_value);
	} catch (err) {
		return default_value;
	}
}

function isObjectsEquel(obj1, obj2) {
	return JSON.stringify(obj1) === JSON.stringify(obj2)
}
// Utils End