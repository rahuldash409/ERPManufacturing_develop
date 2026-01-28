// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Daily Production Manpower"] = {
	"filters": [
		{
			fieldname:"date",
			label:"Date",
			fieldtype:"Date",
			default:frappe.datetime.now_date()
		}
	]
};
