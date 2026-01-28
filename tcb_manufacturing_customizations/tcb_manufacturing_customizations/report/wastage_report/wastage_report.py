# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    filters = filters or {}
    
    columns = [
        {"label":"Dept.","fieldname":"department","fieldtype":"Link","options":"Workstation","width":150},
        {"label":"UOM","fieldname":"uom","fieldtype":"Link","options":"UOM","width":150},
        {"label":"Production","fieldname":"production","fieldtype":"Float","width":150},
        {"label":"Production Today","fieldname":"today_production","fieldtype":"Float","width":150},
        {"label":"Production ToDate","fieldname":"todate_production","fieldtype":"Float","width":150},
        {"label":"Production in KG","fieldname":"kg_production","fieldtype":"Float","width":150},
        {"label":"Production Today in KG.","fieldname":"today_kg_production","fieldtype":"Float","width":150},
        {"label":"Production ToDate in KG","fieldname":"todate_kg_production","fieldtype":"Float","width":150},
        {"label":"Waste in KG.","fieldname":"kg_waste","fieldtype":"Float","width":150},
        {"label":"Waste ToDate in KG.","fieldname":"todate_kg_waste","fieldtype":"Float","width":150},
        {"label":"Percent of Waste","fieldname":"percent_waste","fieldtype":"Percent","options":"Operation","width":150},
        {"label":"Percent of Waste Today.","fieldname":"percent_today_waste","fieldtype":"Percent","width":150},
        {"label":"Percent of Waste ToDate","fieldname":"percent_todate_waste","fieldtype":"Percent","width":150},
        {"label":"Target","fieldname":"target","fieldtype":"Percent","width":150},
    ]
 
    data = []
    
    job_cards = frappe.db.get_all(
        "Job Card",
        filters={
            "status":"Completed",
            "custom_stock_entry_reference":["!=",""],
            "posting_date":["between",[filters.get("from_date"),filters.get("to_date")]]
        },
        fields=["*"]
    )
    
    dept = {}
    for entry in job_cards:
        item = frappe.get_doc("Item",entry.production_item)
        wkn = frappe.get_doc("Workstation",entry.workstation)
        kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"),None)
        se = frappe.get_doc("Stock Entry",entry.custom_stock_entry_reference)
        wastage = sum(itm.qty for itm in se.items if itm.is_scrap_item)
        if entry.workstation not in dept:
            dept[entry.workstation] = {
                # "total_completed_qty":entry.total_completed_qty,
                "department":entry.workstation,
                "uom":item.stock_uom,
                "production":0,
                "today_production":0,
                "kg_production":0,
                "todate_production":0,
                "today_kg_production":0,
                "todate_kg_production":0,
                "kg_waste":0,
                "todate_kg_waste":0,
                "percent_waste":0,
                "percent_today_waste":0,
                "percent_todate_waste":0,
                "target":wkn.custom_target_wastage or 0
            }
        dept[entry.workstation]["production"] += entry.total_completed_qty
        dept[entry.workstation]["today_production"] += entry.total_completed_qty
        if kg_conversion:
            dept[entry.workstation]["today_kg_production"] += entry.total_completed_qty * kg_conversion
            dept[entry.workstation]["kg_production"] += entry.total_completed_qty * kg_conversion
        dept[entry.workstation]["kg_waste"]+=wastage
        if dept[entry.workstation]["today_kg_production"]:
            dept[entry.workstation]["percent_waste"] = (dept[entry.workstation]["kg_waste"] / dept[entry.workstation]["today_kg_production"]) * 100
            dept[entry.workstation]["percent_today_waste"] = (dept[entry.workstation]["kg_waste"] / dept[entry.workstation]["today_kg_production"]) * 100
        if not dept[entry.workstation]["today_kg_production"]:
            dept[entry.workstation]["percent_waste"] = 0
            dept[entry.workstation]["percent_today_waste"] = 0
            
    for key, vals in dept.items():
        jcs_by_opn = frappe.db.get_all("Job Card",filters={
            "workstation":vals["department"],
            "status":"Completed",
            "custom_stock_entry_reference":["!=",""],
            "posting_date":["<=",filters.get("to_date")]
            },
            fields=["custom_stock_entry_reference","total_completed_qty","production_item","workstation"]
        )
        todate_production = 0
        todate_kg_production = 0
        todate_waste = 0
        
        for jc in jcs_by_opn:
            item = frappe.get_doc("Item",jc.production_item)
            kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"),None)
            se= frappe.get_doc("Stock Entry",jc.custom_stock_entry_reference)
            waste = sum(itm.qty for itm in se.items if itm.is_scrap_item)
            
            todate_production +=jc.total_completed_qty
            if kg_conversion:
                todate_kg_production += jc.total_completed_qty * kg_conversion
            todate_waste += waste
            
        vals["todate_production"] = todate_production
        vals["todate_kg_production"] = todate_kg_production
        vals["todate_kg_waste"] = todate_waste
        
        if todate_kg_production:
            vals["percent_todate_waste"] = ((todate_waste/todate_kg_production) * 100)
        if not todate_kg_production:
            vals["percent_todate_waste"] = 0
        
        data.append(vals)
    return columns, data
