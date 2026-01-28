// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt
const repairables = "Repairable Spares"
const consumables = "Consumable Spares"


frappe.query_reports["Spare Parts Report"] = {
	"filters": [
        {
			fieldname: "spare_report_type",
			label: __("Spare Report Type"),
			fieldtype: "Select",
			width: "80",
			options: [
					{ value: repairables, description: repairables },
                    { value: consumables, description: consumables },
                    ],
			default: consumables,
            onchange: function() {
                refresh()
                // let spare_type = frappe.query_reports.get_filter_value('spare_report_type');
                
                // let status_filter = frappe.query_reports.get_filter('spare_status');
                // if (status_filter) {
                //     if (spare_type === consumables) {
                //         status_filter.df.hidden = 1;
                //         status_filter.refresh();
                //     } else {
                //         status_filter.df.hidden = 0;
                //         status_filter.refresh();
                //     }
                // }
                
                let spare_part_filter = frappe.query_report.get_filter('spare_part');
                if (spare_part_filter) {
                    spare_part_filter.refresh();
                    // spare_part_filter = ""
                    frm.refresh_field('spare_part')
                }
                
                frappe.query_report.refresh();
            }
            
		},
        {
			fieldname: "workstation",
			label: __("Workstation"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Workstation",
            get_data: (txt) => {
				return frappe.db.get_link_options("Workstation");
			},
			// default: frappe.defaults.get_default("company"),
		},

        {
			fieldname: "spare_part",
			label: __("Spare Part"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: "Item",
            get_data: (txt) => {
                let spare_type = frappe.query_report.get_filter_value('spare_report_type');
                    return frappe.db.get_link_options("Item", txt, {
                    item_group: spare_type || consumables
                });
            },
			// default: frappe.defaults.get_default("company"),
		},

        {
			fieldname:"entry_date_range",
			label:"Date Range",
			fieldtype:"Date Range",
			default: [
                    frappe.datetime.add_months(frappe.datetime.get_today(), -2),
                    frappe.datetime.get_today()
                ],
            // on_change: function() {
            //     console.log('eyerehreirehwiowheorihfosdlkfhskl-=-=-=====')
            //     frappe.query_report.refresh();
            //     // refresh()
            // }
		},

        {
			fieldname: "spare_status",
			label: __("Status"),
			fieldtype: "MultiSelectList",
			width: "80",
			options: [
					{ value: "Installation Pending", description: "Installation Pending" },
                    { value: "In Use", description: "In Use" },
                    { value: "Scrapped", description: "Scrapped" },
                    { value: "Sent For Repair", description: "Sent For Repair" },
                    { value: "Available", description: "Available" },
                    { value: "Used In another Workstation", description: "Used In another Workstation" },
                    ],
			default: "In Use",
            // hidden:0
		},
        

		// {
		// 	fieldname:"dispose_replacement_date_range",
		// 	label:"Dispose/Replacement Date Range",
		// 	fieldtype:"Date Range",
		// 	// default:frappe.datetime.get_today()
		// },
	],
    after_datatable_render: function(datatable) {
        let report = frappe.query_report;
        // console.log(" here is the rpeot ===",report)
        report.page.set_indicator(`Total Records ${report.raw_data.message.total_records}`, "blue");

    },
    onload: function(report){
        frappe.query_report.set_filter_value('spare_status', ['In Use']);
        // setTimeout(() => {
        //     console.log('Raw data:', report.raw_data);
        //     console.log('Message:', report.raw_data.message);
            
        //     if (report.raw_data && report.raw_data.message) {
        //     if (report.raw_data && report.raw_data.message) {
        //         let total_records = report.raw_data.message.total_records || report.raw_data.message;
        //         console.log('Total records:', total_records);
        //         report.page.set_indicator(`Total ${total_records}`, "blue");
        //     }
        // }}, 1000);
        // // if (status_filter && spare_type === consumables) {
        // //     status_filter.df.hidden = 1;
        // //     status_filter.refresh();
        // // }
    }
,
	formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (data && data.spare_status) {
        let bgColor = '';

        switch (data.spare_status) {
            case "Installation Pending":
                bgColor = "#d1ecf1";   // Light Cyan
                break;

            case "In Use":
                bgColor = "#d4edda";   // Light Green
                break;

            case "Scrapped":
                bgColor = "#f8d7da";   // Light Red
                break;

            case "Sent For Repair":
                bgColor = "#fff3cd";   // Light Yellow
                break;

            case "Available":
                bgColor = "#e2e3e5";   // Light Grey
                break;

            case "Used In another Workstation":
                bgColor = "#f8fce4ff";   // Light Pink
                break;
            // give a color to status = damaged 
            case "Damaged":
                bgColor = "#f5c6cb";   // Light Coral
                break;
        }

        if (bgColor) {
            value = `<span style="background-color:${bgColor}; padding:3px; display:block;">${value}</span>`;
        }
    }

        return value;
	}
};

