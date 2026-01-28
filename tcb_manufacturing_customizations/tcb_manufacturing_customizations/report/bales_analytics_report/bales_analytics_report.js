// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Bales Analytics Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1
		},
		{
			fieldname: "source",
			label: __("Source"),
			fieldtype: "Select",
			options: "\nManufacture\nImport",
			on_change: function() {
				// Refresh report when source changes
				frappe.query_report.refresh();
			}
		},
		{
			fieldname: "bales_status",
			label: __("Bale Status"),
			fieldtype: "Select",
			options: "\nRequire Packing\nPacked In House\nNeed Approval\nPacked Import\nDispatched"
		},
		{
			fieldname: "item",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			get_query: function() {
				return {
					filters: {
						"custom_bale_qty": [">", 0]
					}
				};
			}
		},
		{
			fieldname: "batch",
			label: __("Batch"),
			fieldtype: "Link",
			options: "Batch"
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse"
		}
	],

	onload: function(report) {
		// Add custom buttons for additional charts
		report.page.add_inner_button(__("Show All Charts"), function() {
			show_all_charts(report);
		});
	},

	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Apply color coding for status
		if (column.fieldname === "bales_status" && value) {
			const status_colors = {
				"Require Packing": "orange",
				"Packed In House": "yellow",
				"Need Approval": "blue",
				"Packed Import": "green",
				"Dispatched": "purple"
			};

			const color = status_colors[data.bales_status];
			if (color) {
				value = `<span class="indicator-pill ${color}">${value}</span>`;
			}
		}

		// Bold parent rows (Bales Creator level)
		if (data && data.is_group === 1) {
			if (column.fieldname === "bales_creator_id" ||
				column.fieldname === "item" ||
				column.fieldname === "quantity" ||
				column.fieldname === "total_bales_count") {
				value = `<strong>${value}</strong>`;
			}
		}

		// Indent child rows
		if (data && data.indent === 1 && column.fieldname === "bale_id") {
			value = `<span style="padding-left: 20px;">${value}</span>`;
		}

		return value;
	},

	get_datatable_options(options) {
		return Object.assign(options, {
			treeView: true,
			checkboxColumn: false
		});
	},

	initial_depth: 0
};


function show_all_charts(report) {
	// Get current filters
	const filters = report.get_values();

	frappe.call({
		method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.report.bales_analytics_report.bales_analytics_report.get_additional_charts",
		args: {
			filters: filters
		},
		callback: function(r) {
			if (r.message && r.message.length > 0) {
				show_charts_dialog(r.message);
			} else {
				frappe.msgprint(__("No chart data available for the selected filters."));
			}
		}
	});
}


function show_charts_dialog(charts) {
	// Create dialog with multiple charts
	const dialog = new frappe.ui.Dialog({
		title: __("Bales Analytics Charts"),
		size: "extra-large",
		fields: [
			{
				fieldname: "charts_html",
				fieldtype: "HTML"
			}
		]
	});

	// Build HTML for charts
	let charts_html = '<div class="row">';

	charts.forEach((chart_data, index) => {
		const chart_id = `analytics-chart-${index}`;
		charts_html += `
			<div class="col-md-6 mb-4">
				<div class="card">
					<div class="card-header">
						<h5 class="mb-0">${chart_data.title}</h5>
					</div>
					<div class="card-body">
						<div id="${chart_id}" style="height: 250px;"></div>
					</div>
				</div>
			</div>
		`;
	});

	charts_html += '</div>';

	dialog.fields_dict.charts_html.$wrapper.html(charts_html);
	dialog.show();

	// Render charts after dialog is shown
	setTimeout(() => {
		charts.forEach((chart_data, index) => {
			const chart_id = `analytics-chart-${index}`;
			const chart_container = document.getElementById(chart_id);

			if (chart_container) {
				new frappe.Chart(chart_container, {
					data: chart_data.data,
					type: chart_data.type,
					colors: chart_data.colors,
					height: 230,
					axisOptions: {
						xAxisMode: "tick",
						xIsSeries: false
					},
					barOptions: {
						stacked: false,
						spaceRatio: 0.3
					}
				});
			}
		});
	}, 300);
}
