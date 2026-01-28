// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt

frappe.query_reports["Production Master"] = {
	"filters": [
		{
			fieldname:"department",
			label:"Department",
			fieldtype:"Select",
			options:"Printing\nSlitting\nAD*STARKON\nSegregation\nPackaging",
			default:"Printing"
		},
		{
			fieldname:"from_date",
			label:"Start Date",
			fieldtype:"Date",
			default:frappe.datetime.get_today()
		},
		{
			fieldname:"to_date",
			label:"End Date",
			fieldtype:"Date",
			default:frappe.datetime.get_today()
		},
		{
			fieldname:"specific_dept",
			label:"Specific Department",
			fieldtype:"Select",
			options:"Production\nPower\nWastage\nBOM vs Actual",
			default:"Production"
		}
	]
};
