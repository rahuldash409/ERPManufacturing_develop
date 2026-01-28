// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt

// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors and contributors
// For license information, please see license.txt


// else{
// frm.set_value('from_warehouse',spares_transfer_source_warehouse_name)
// }
frappe.query_reports["Alliance Spares Balance"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			width: "80",
			options: "Company",
			default: frappe.defaults.get_default("company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
			hidden:1,
			// default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("Till Date"),
			fieldtype: "Date",
			width: "80",
			reqd: 1,
			default: frappe.datetime.get_today(),
		},
		// {
		// 	fieldname: "item_group",
		// 	label: __("Item Group"),
		// 	fieldtype: "Link",
		// 	width: "80",
		// 	options: "Item Group",
		// },
		{
			fieldname: "item_code",
			label: __("Items"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Item",
            get_data: (txt) => {
                    return frappe.db.get_link_options("Item", txt, {
                    item_group: ['like','%spare%']
                });
            },
			// default: frappe.defaults.get_default("company"),
		},

		{
			fieldname: "warehouse",
			label: __("Warehouses"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Warehouse",
			get_data: async (txt) => {
				return frappe.db.get_link_options("Warehouse", txt);
			},
		},
		// {
		// 	fieldname: "warehouse_type",
		// 	label: __("Warehouse Type"),
		// 	fieldtype: "Link",
		// 	width: "80",
		// 	options: "Warehouse Type",
		// },
		{
			fieldname: "valuation_field_type",
			label: __("Valuation Field Type"),
			fieldtype: "Select",
			width: "80",
			options: "Currency\nFloat",
			default: "Currency",
			hidden:true,
		},
		// {
		// 	fieldname: "include_uom",
		// 	label: __("Include UOM"),
		// 	fieldtype: "Link",
		// 	options: "UOM",
		// },
		// {
		// 	fieldname: "show_variant_attributes",
		// 	label: __("Show Variant Attributes"),
		// 	fieldtype: "Check",
		// },
		// {
		// 	fieldname: "show_stock_ageing_data",
		// 	label: __("Show Stock Ageing Data"),
		// 	fieldtype: "Check",
		// },
		// {
		// 	fieldname: "ignore_closing_balance",
		// 	label: __("Ignore Closing Balance"),
		// 	fieldtype: "Check",
		// 	default: 0,
		// },
		// {
		// 	fieldname: "include_zero_stock_items",
		// 	label: __("Include Zero Stock Items"),
		// 	fieldtype: "Check",
		// 	default: 0,
		// },
		// {
		// 	fieldname: "show_dimension_wise_stock",
		// 	label: __("Show Dimension Wise Stock"),
		// 	fieldtype: "Check",
		// 	default: 0,
		// },
	],
	onload:async function(report){
	const spares_settings_doc = await frappe.db.get_doc('Workstation Spares Settings','Workstation Spares Settings',);
	const default_racks_warehouse_name =  spares_settings_doc.default_racks_warehouse
	if (!default_racks_warehouse_name){
	frappe.throw({
		title: `Default Racks Warehouse Missing`,
		message: `
			<b>Default Racks Warehouse is not configured!</b><br><br>
					Please set the <b>Default Racks Warehouse</b> in the 
					<b>Workstation Spares Settings</b> before performing this action.<br><br>
					👉 <a href="/app/workstation-spares-settings/Workstation%20Spares%20Settings" 
					target="_blank" 
					style="font-weight:600; color:#2980b9;">
						Open Workstation Spares Settings
					</a>
				`
	});
	return;
	}
	frappe.query_report.set_filter_value('warehouse',default_racks_warehouse_name );
	// report.warehouse = default_racks_warehouse_name;
	// repo
	// .set_filter_value("warehouse",default_racks_warehouse_name)

	},
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "out_qty" && data && data.out_qty > 0) {
			value = "<span style='color:red'>" + value + "</span>";
		} else if (column.fieldname == "in_qty" && data && data.in_qty > 0) {
			value = "<span style='color:green'>" + value + "</span>";
		}

		return value;
	},
};

erpnext.utils.add_inventory_dimensions("Alliance Stock Balance", 8);
