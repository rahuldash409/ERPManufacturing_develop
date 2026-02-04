// Copyright (c) 2026, rahul.dash@spplgroup.com and contributors
// For license information, please see license.txt

frappe.query_reports["Raw Material Consumption"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            reqd: 1
        }
    ]
};