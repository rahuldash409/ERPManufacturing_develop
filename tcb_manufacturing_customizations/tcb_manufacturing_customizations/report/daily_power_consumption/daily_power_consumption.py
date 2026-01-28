# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    filters = filters or {}
    columns =[
        {"fieldname":"date","label":"Date","fieldtype":"Date","width":150},
        {"fieldname":"workstation","label":"Workstation","fieldtype":"Link","options":"Workstation","width":160},
        {"fieldname":"ipc_unit","label":"IPC. Unit Cons.","fieldtype":"Float","width":160},
        {"fieldname":"ipc_prod","label":"IPC. Production","fieldtype":"Float","width":160},
        {"fieldname":"ipc_cost","label":"IPC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"uom","label":"UOM","fieldtype":"Link","options":"UOM","width":160},
        {"fieldname":"today_apc_unit","label":"Today APC. Unit Cons.","fieldtype":"Float","width":160},
        {"fieldname":"today_apc_prod","label":"Today APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"today_apc_cost","label":"Today APC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"apc_unit","label":"Todate APC. Unit Cons.","fieldtype":"Float","width":160},
        {"fieldname":"apc_prod","label":"Todate APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"apc_cost","label":"Todate APC. Unit Cost","fieldtype":"Float","width":160},
    ]
    data = []
    
    job_cards = frappe.db.get_all("Job Card",
                                  filters={
                                      "status":"Completed",
                                      "custom_stock_entry_reference":["!=",""],
                                      "posting_date":["between",[filters.get("from_date"),filters.get("to_date")]]
                                  },
                                  fields = ["production_item","workstation","total_completed_qty","posting_date"]
                                  )
    workstation={}
    
    for jc in job_cards:
        workstn = frappe.get_doc("Workstation",jc.workstation)
        units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jc.workstation},fields=["unit_consumption"],limit=1)
        itm = frappe.get_doc("Item",jc.production_item)
        if jc.workstation not in workstation:
            workstation[jc.workstation] = {
                "date":jc.posting_date,
                "workstation":jc.workstation,
                "ipc_unit":workstn.custom_ideal_unit_consumption,
                "ipc_prod":workstn.custom_ideal_production,
                "ipc_cost":workstn.custom_ideal_unit_cost,
                "uom":f"Units/{itm.stock_uom}",
                "today_apc_unit":0,
                "today_apc_prod":0,
                "today_apc_cost":0,
                "apc_unit":0,
                "apc_prod":0,
                "apc_cost":0
            }
        workstation[jc.workstation]["today_apc_unit"] += units[0].get("unit_consumption") if units else 0
        workstation[jc.workstation]["today_apc_prod"] += jc.total_completed_qty
    
    todate_jc = frappe.db.get_all("Job Card",
                                  filters={
                                      "status":"Completed",
                                      "custom_stock_entry_reference":["!=",""],
                                      "posting_date":["<=",filters.get("to_date")]
                                  },
                                  fields = ["production_item","workstation","total_completed_qty","posting_date"])
    for jcard in todate_jc:
        units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jcard.workstation},fields=["unit_consumption"],limit=1)
        
        if jcard.workstation in workstation:            
            workstation[jcard.workstation]["apc_unit"] += units[0].get("unit_consumption") if units else 0
            workstation[jcard.workstation]["apc_prod"] += jcard.total_completed_qty
    
    
    for wrkstn, vals in workstation.items():
        workstation[wrkstn]["today_apc_cost"] = vals["today_apc_unit"]/vals["today_apc_prod"] if vals["today_apc_prod"] else 0
        workstation[wrkstn]["apc_cost"] = vals["apc_unit"]/vals["apc_prod"] if vals["apc_prod"] else 0
        data.append(vals)
 
    return columns, data

