// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Daily Power Consumption"] = {
	"filters": [
		{
			fieldname:"from_date",
			label:"From Date",
			fieldtype:"Date",
			default:frappe.datetime.get_today()
		},
		{
			fieldname:"to_date",
			label:"To Date",
			fieldtype:"Date",
			default:frappe.datetime.get_today()
		}
	]
};
