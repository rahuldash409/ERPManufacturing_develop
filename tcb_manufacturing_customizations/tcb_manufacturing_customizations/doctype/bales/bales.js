// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bales", {
	refresh(frm) {
		// Show status indicator
		if (frm.doc.bales_status) {
			let status_colors = {
				'Require Packing': 'orange',
				'Packed In House': 'yellow',
				'Need Approval': 'blue',
				'Packed Import': 'green',
				'Dispatched': 'purple',
				'Re-Packed': 'grey'
			};
			let color = status_colors[frm.doc.bales_status] || 'grey';
			frm.dashboard.add_indicator(__('Status: {0}', [frm.doc.bales_status]), color);
		}

		// Add status transition buttons based on current status
		if (frm.doc.docstatus === 1) {
			add_status_buttons(frm);
		}

		// Show linked documents
		if (frm.doc.material_consumption_entry) {
			frm.add_custom_button(__('View Stock Entry'), function() {
				frappe.set_route('Form', 'Stock Entry', frm.doc.material_consumption_entry);
			}, __('Links'));
		}

		if (frm.doc.delivery_note) {
			frm.add_custom_button(__('View Delivery Note'), function() {
				frappe.set_route('Form', 'Delivery Note', frm.doc.delivery_note);
			}, __('Links'));
		}

		if (frm.doc.source_document && frm.doc.source_document_type) {
			frm.add_custom_button(__('View {0}', [frm.doc.source_document_type]), function() {
				frappe.set_route('Form', frm.doc.source_document_type, frm.doc.source_document);
			}, __('Links'));
		}
	},
});

function add_status_buttons(frm) {
	let status = frm.doc.bales_status;

	// Define allowed transitions
	let transitions = {
		'Require Packing': [{ label: 'Mark as Packed In House', next: 'Packed In House', color: 'btn-warning' }],
		'Packed In House': [
			{ label: 'Request Approval', next: 'Need Approval', color: 'btn-primary' },
			{ label: 'Revert to Require Packing', next: 'Require Packing', color: 'btn-default' }
		],
		'Need Approval': [
			{ label: 'Approve (Packed Import)', next: 'Packed Import', color: 'btn-success' },
			{ label: 'Reject (Back to Packed In House)', next: 'Packed In House', color: 'btn-danger' }
		],
		'Packed Import': [],  // Dispatched is handled by Delivery Note
		'Dispatched': [],  // Revert is handled by Delivery Note cancel
		'Re-Packed': []  // Final status - no further transitions
	};

	let available_transitions = transitions[status] || [];

	available_transitions.forEach(function(transition) {
		frm.add_custom_button(__(transition.label), function() {
			update_status(frm, transition.next);
		}, __('Status')).addClass(transition.color);
	});
}

function update_status(frm, new_status) {
	frappe.confirm(
		__('Are you sure you want to change status to {0}?', [new_status]),
		function() {
			frappe.call({
				method: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.bales.bales.update_bales_status',
				args: {
					bales_name: frm.doc.name,
					new_status: new_status
				},
				freeze: true,
				freeze_message: __('Updating status...'),
				callback: function(r) {
					if (r.message && r.message.success) {
						frappe.show_alert({
							message: __(r.message.message),
							indicator: 'green'
						});
						frm.reload_doc();
					}
				}
			});
		}
	);
}

frappe.ui.form.on("Bales Batches", {
	batches_used_add(frm, cdt, cdn) {
		let item = getAttr(frm.doc, "item", null);
		if (item) {
			frappe.model.set_value(cdt, cdn, "item", item);
		}
		// Set warehouse from parent
		if (frm.doc.warehouse) {
			frappe.model.set_value(cdt, cdn, "warehouse", frm.doc.warehouse);
		}
	},
	item(frm, cdt, cdn) {
		let item = getAttr(frm.doc, "item", null);
		if (item) {
			frappe.model.set_value(cdt, cdn, "item", item)
		}
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
