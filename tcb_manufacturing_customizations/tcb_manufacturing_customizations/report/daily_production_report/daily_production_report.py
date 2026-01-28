# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    filters = filters or {}

    columns = [
        {"label":"Date","fieldname":"date","fieldtype":"Date","width":120},
        {"label":"Machine (Workstation)","fieldname":"machine","fieldtype":"Link","options":"Workstation","width":200},
        {"label":"Designed Capacity (24Hr)","fieldname":"designed_capacity","fieldtype":"Data","width":150},
        {"label":"UOM","fieldname":"uom","fieldtype":"Link","options":"UOM","width":100},
        {"label":"Production","fieldname":"production","fieldtype":"Data","width":160},
        {"label":"Efficiency","fieldname":"efficiency","fieldtype":"Percent","width":100},
        {"label":"Total","fieldname":"total","fieldtype":"Float","width":160},
        {"label":"Production To Date","fieldname":"production_to_date","fieldtype":"Float","width":160},
    ]
    data = []
    
    rows = {}
    cumulative = {}
    job_cards = frappe.db.get_all(
        "Job Card",
        filters={
            "status": "Completed",
            "custom_stock_entry_reference": ["!=", ""],
            "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]]
        },
        fields=["workstation","operation","bom_no","posting_date","custom_shift","total_completed_qty","production_item"],
        order_by="posting_date asc"
    )
    
    for jc in job_cards:
        job_capacity = frappe.db.get_value("Workstation",jc.workstation,"custom_job_capacity")
        uom = frappe.db.get_value("Item",jc.production_item,"stock_uom")
        
        if jc.workstation not in cumulative:
            cumulative[jc.workstation] = 0
        cumulative[jc.workstation]+=jc.total_completed_qty
        
        rows = {
            "date":jc.posting_date,
            "machine":jc.workstation,
            "designed_capacity":job_capacity,
            "uom":uom,
            "production":jc.total_completed_qty,
            "efficiency":(jc.total_completed_qty/job_capacity)*100,
            "total":jc.total_completed_qty,
            "production_to_date":cumulative[jc.workstation]
        }
        data.append(rows)

    return columns, data











# GROUPED BY OPERATION AND WORKSTATION. DONT NEED IT NOW
# def execute(filters=None):
#     filters = filters or {}
    
#     columns = [
#         {"label":"Date","fieldname":"date","fieldtype":"Date","width":120},
#         {"label":"Department","fieldname":"department","fieldtype":"Link","options":"Operation","width":100},
#         {"label":"Designed Capacity (24Hr)","fieldname":"designed_capacity","fieldtype":"Data","width":150},
#         {"label":"UOM","fieldname":"uom","fieldtype":"Link","options":"UOM","width":100},
#         {"label":"Machine (Workstation)","fieldname":"machine","fieldtype":"Link","options":"Workstation","width":200},
#         {"label":"Shift","fieldname":"shift","fieldtype":"Data","width":160},
#         {"label":"Efficiency","fieldname":"efficiency","fieldtype":"Percent","width":100},
#         {"label":"Total","fieldname":"total","fieldtype":"Data","width":160},
#     ]
#     data = []
    
#     job_cards = frappe.db.get_all(
#         "Job Card",
#         filters={
#             "status": "Completed",
#             "custom_stock_entry_reference": ["!=", ""],
#             "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]]
#         },
#         fields=["workstation","operation","bom_no","posting_date","custom_shift","total_completed_qty"]
#     )
    
#     jobs = {}
    
#     for card in job_cards:
#         key = (card.operation, card.workstation) 
        
#         if key not in jobs:
#             jobs[key] = {
#                 "shift": 0,
#                 "posting_date": card.posting_date,
#                 "department": card.operation,
#                 "machine": card.workstation,
#                 "bom_no": card.bom_no
#             }
#         jobs[key]["shift"] += card.total_completed_qty
    
#     for (operation, workstation_name), info in jobs.items():
#         workstation = frappe.get_doc("Workstation", info["machine"])
#         bom = frappe.get_doc("BOM", info["bom_no"])
        
#         efficiency = 0
#         if workstation.custom_job_capacity:
#             efficiency = (info["shift"] / workstation.custom_job_capacity) * 100
        
#         recs = {
#             "date": info["posting_date"],
#             "department": info["department"],
#             "designed_capacity": workstation.custom_job_capacity,
#             "uom": bom.uom,
#             "machine": info["machine"],
#             "shift": info["shift"],
#             "efficiency": efficiency,
#             "total": info["shift"]
#         }    
    
#         data.append(recs)
    
#     return columns, data


    
    