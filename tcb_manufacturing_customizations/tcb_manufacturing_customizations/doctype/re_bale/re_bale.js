// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Re-Bale", {
	setup(frm) {
		// Set default raw_material_warehouse from TCB Settings
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "TCB Settings",
				fieldname: ["custom_default_bales_warehouse"],
			},
			callback: function (r) {
				if (r.message && r.message.custom_default_bales_warehouse) {
					frm.default_warehouse = r.message.custom_default_bales_warehouse;
				} else {
					frm.default_warehouse = "Segregation Warehouse - APUI";
				}
				// Set default raw_material_warehouse
				frm.default_raw_material_warehouse = "Raw Material - APUI";
			},
		});
	},

	refresh(frm) {
		// Set filters for original_bale field
		frm.set_query("original_bale", function () {
			return {
				filters: {
					docstatus: 1,
					bales_status: ["in", ["Packed Import", "Packed In House"]],
				},
			};
		});

		// Set defaults for new documents
		if (frm.is_new()) {
			if (frm.default_raw_material_warehouse && !frm.doc.raw_material_warehouse) {
				frm.set_value("raw_material_warehouse", frm.default_raw_material_warehouse);
			}
		}

		// Show links after submission
		if (frm.doc.docstatus === 1) {
			if (frm.doc.stock_entry) {
				frm.add_custom_button(
					__("View Stock Entry"),
					function () {
						frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
					},
					__("Links")
				);
			}

			if (frm.doc.new_bale) {
				frm.add_custom_button(
					__("View New Bale"),
					function () {
						frappe.set_route("Form", "Bales", frm.doc.new_bale);
					},
					__("Links")
				);
			}

			if (frm.doc.original_bale) {
				frm.add_custom_button(
					__("View Original Bale"),
					function () {
						frappe.set_route("Form", "Bales", frm.doc.original_bale);
					},
					__("Links")
				);
			}
		}

		// Show dashboard indicator
		if (frm.doc.docstatus === 1 && frm.doc.stock_entry) {
			frappe.db.get_value("Stock Entry", frm.doc.stock_entry, "docstatus", (r) => {
				if (r && r.docstatus !== undefined) {
					let status_text, color;
					if (r.docstatus === 0) {
						status_text = "Stock Entry: Draft";
						color = "orange";
					} else if (r.docstatus === 1) {
						status_text = "Stock Entry: Submitted";
						color = "green";
					} else {
						status_text = "Stock Entry: Cancelled";
						color = "red";
					}
					frm.dashboard.add_indicator(__(status_text), color);
				}
			});
		}
	},

	original_bale(frm) {
		if (frm.doc.original_bale) {
			frappe.call({
				method:
					"tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.re_bale.re_bale.get_bale_details",
				args: {
					bale_name: frm.doc.original_bale,
				},
				freeze: true,
				freeze_message: __("Fetching bale details..."),
				callback: function (r) {
					if (r.message) {
						let data = r.message;

						// Set parent fields
						frm.set_value("item_code", data.item_code);
						frm.set_value("item_name", data.item_name);
						frm.set_value("warehouse", data.warehouse);
						frm.set_value("original_qty", data.original_qty);
						frm.set_value("new_qty", data.original_qty);

						// Clear and populate batches table
						frm.clear_table("batches");

						data.batches.forEach(function (batch) {
							let row = frm.add_child("batches");
							row.batch = batch.batch;
							row.sub_batch = batch.sub_batch;
							row.original_qty = batch.original_qty;
							row.new_qty = batch.new_qty;
							row.item = batch.item;
							row.warehouse = batch.warehouse;
						});

						frm.refresh_field("batches");

						frappe.show_alert({
							message: __("Bale details loaded. Edit batch quantities as needed."),
							indicator: "green",
						});
					}
				},
			});
		} else {
			// Clear fields when original_bale is cleared
			frm.set_value("item_code", null);
			frm.set_value("item_name", null);
			frm.set_value("warehouse", null);
			frm.set_value("original_qty", 0);
			frm.set_value("new_qty", 0);
			frm.clear_table("batches");
			frm.refresh_field("batches");
		}
	},
});

frappe.ui.form.on("Re-Bale Item", {
	new_qty(frm, cdt, cdn) {
		// Recalculate total new_qty when any batch qty changes
		calculate_total_new_qty(frm);

		// Validate new_qty doesn't exceed original_qty
		let row = locals[cdt][cdn];
		if (flt(row.new_qty) > flt(row.original_qty)) {
			frappe.msgprint({
				title: __("Validation Error"),
				message: __("New Qty cannot exceed Original Qty ({0})", [row.original_qty]),
				indicator: "red",
			});
			frappe.model.set_value(cdt, cdn, "new_qty", row.original_qty);
		}
	},

	batches_remove(frm) {
		calculate_total_new_qty(frm);
	},
});

function calculate_total_new_qty(frm) {
	let total = 0;
	(frm.doc.batches || []).forEach(function (row) {
		total += flt(row.new_qty);
	});
	frm.set_value("new_qty", total);
}
