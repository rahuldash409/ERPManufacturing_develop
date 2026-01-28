// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bales Creator", {
	setup(frm) {
		// Fetch default warehouse from TCB Settings
		frappe.db.get_single_value("TCB Settings", "default_bales_warehouse").then((default_warehouse) => {
			if (default_warehouse && !frm.doc.warehouse) {
				frm.set_value("warehouse", default_warehouse);
			}
		});

		// if(!frm.get_field("warehouse").value){
		// 	frm.set_value("warehouse","Segregation Warehouse - APUI")
		// }

		// if(!frm.get_field("raw_material_warehouse").value){
		// 	frm.set_value("raw_material_warehouse","Raw Material - APUI")
		// }
	},


	// method present at -> frappe/frappe/public/js/frappe/form/grid_row.js
    // (show, below, duplicate)
	number_of_bales: function(frm){
		let copies_needed = frm.get_field("number_of_bales").value
		let grid = frm.fields_dict["items"].grid;
		let grid_rows = grid.grid_rows;
		for(let i =0;i<copies_needed-1;i++){
			grid_rows[0].insert(false, true, true);
		}
		frm.refresh_field("items")
	},

	refresh(frm) {
		// Set filters for item_code to only show items with custom_bale_qty > 0
		frm.set_query("item_code", function() {
			return {
				filters: {
					"custom_bale_qty": [">", 0],
					"item_group": "packaged ad*star bags",
				}
			};
		});

		// Filter material_receipts to show only "Material Receipt" stock entries
		if (frm.fields_dict.material_receipts) {
			frm.fields_dict.material_receipts.get_query = function() {
				return {
					filters: {
						"stock_entry_type": "Material Receipt",
						"docstatus": 1
					}
				};
			};
		}

		// Add buttons for submitted Bales Creator
		if (frm.doc.docstatus >= 1) {
			// View Stock Entry button - only if stock_entry exists
			if (frm.doc.stock_entry) {
				frm.add_custom_button(__('Stock Entry'), function() {
					frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
				}, __("View"));

				// Show Stock Entry status on dashboard
				frappe.db.get_value("Stock Entry", frm.doc.stock_entry, "docstatus", function(r) {
					if (r && r.docstatus !== undefined) {
						let status_text = r.docstatus === 1 ? "Submitted" : (r.docstatus === 0 ? "Draft" : "Cancelled");
						let indicator = r.docstatus === 1 ? "green" : (r.docstatus === 0 ? "orange" : "red");
						frm.dashboard.add_indicator(
							__('Stock Entry: {0} ({1})', [frm.doc.stock_entry, status_text]),
							indicator
						);
					}
				});
			}

			// View linked Bales button
			frm.add_custom_button(__('Bales'), function() {
				frappe.set_route("List", "Bales", {
					"source_document_type": "Bales Creator",
					"source_document": frm.doc.name
				});
			}, __("View"));
		}
	},

	item_code(frm) {
		// When parent item_code changes, update all child rows
		if (frm.doc.item_code && frm.doc.items && frm.doc.items.length > 0) {
			frm.doc.items.forEach((row) => {
				frappe.model.set_value(row.doctype, row.name, "item_code", frm.doc.item_code);
			});
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

	raw_material_warehouse(frm) {
		// Update warehouse in all child rows when parent warehouse changes
		if (frm.doc.raw_material_warehouse && frm.doc.items && frm.doc.items.length > 0) {
			frm.doc.items.forEach((row) => {
				frappe.model.set_value(row.doctype, row.name, "raw_material_warehouse", frm.doc.raw_material_warehouse);
			});
		}
	}
});


frappe.ui.form.on("Bales Creator Item", {
	items_add(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		// Set item_code from parent
		if (frm.doc.item_code) {
			frappe.model.set_value(cdt, cdn, "item_code", frm.doc.item_code);
		}

		// Set warehouse from parent
		if (frm.doc.warehouse) {
			frappe.model.set_value(cdt, cdn, "warehouse", frm.doc.warehouse);
		}

		// Set RM warehouse from parent
		if (frm.doc.warehouse) {
			frappe.model.set_value(cdt, cdn, "raw_material_warehouse", frm.doc.raw_material_warehouse);
		}
	},

	item_code(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		// Auto-fetch qty from Item.custom_bale_qty
		if (row.item_code) {
			frappe.call({
				method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.bales_creator.bales_creator.get_item_bale_qty",
				args: {
					item_code: row.item_code
				},
				callback(resp) {
					if (resp.message && resp.message > 0) {
						frappe.model.set_value(cdt, cdn, "qty", resp.message);
						// frappe.show_alert({
						// 	message: __("Bale qty auto-fetched: {0}", [resp.message]),
						// 	indicator: 'blue'
						// });
					}
				}
			});
		}
	}
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