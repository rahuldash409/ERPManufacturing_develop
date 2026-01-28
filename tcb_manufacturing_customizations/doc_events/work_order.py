import frappe
import traceback
from frappe import _
import math


# REMOVED WORKING FOR NOW
def check_warehouse(doc, method=None):
    flag = False
    is_bag_mfg = any(
            "Bag Manufacturing" in op.operation
            for op in (doc.operations or [])
        )
    if not is_bag_mfg:
        if not doc.source_warehouse and not doc.scrap_warehouse and doc.bom_no:
            bom = frappe.get_doc("BOM",doc.bom_no)
            if bom.custom_raw_material_warehouse:
                doc.source_warehouse = bom.custom_raw_material_warehouse
                for row in doc.required_items:
                    row.source_warehouse = bom.custom_raw_material_warehouse
                    flag = True
                flag = True
            if bom.custom_scrap_warehouse:
                doc.scrap_warehouse = bom.custom_scrap_warehouse
                flag = True
            if bom.custom_work_in_progress_warehouse:
                doc.wip_warehouse = bom.custom_work_in_progress_warehouse
                flag = True
            if bom.custom_finished_goods_warehouse:
                doc.fg_warehouse  = bom.custom_finished_goods_warehouse
                flag = True
    if flag:
        doc.save()


def before_insert(doc, method=None):
    try:
        doc.transfer_material_against = "Job Card"
        is_bag_mfg = any(
            "Bag Manufacturing" in op.operation
            for op in (doc.operations or [])
        )
        if is_bag_mfg:

            for item in doc.required_items:
                group = frappe.db.get_value("Item", item.item_code, "item_group")
                group_l = group.lower() if group else ""
    
                bom_fetch = frappe.db.get_value(
                    "BOM",
                    {
                        "item": item.item_code,
                        "is_default": 1,
                        "is_active": 1,
                        "docstatus": 1
                    },
                    "custom_finished_goods_warehouse"
                )
                
                if bom_fetch:  
                    item.source_warehouse = bom_fetch
                else:
                    if "fabric" in group_l:
                        item.source_warehouse = "Printing Warehouse - APUI"
    
                    elif "patch" in group_l or "valve" in group_l:
                        item.source_warehouse = "Slitting Warehouse - APUI"
    
                    else:
                        item.source_warehouse = doc.source_warehouse or "Raw Material - APUI"
                
                if item.required_qty:
                    item.required_qty = math.ceil(item.required_qty)
                    
        # if doc.operations:
        #     for opn in doc.operations:
        #         if not opn.workstation:
        #             wkn = frappe.db.get_value("Operation",opn.operation,"workstation")
        #             opn.workstation = wkn or ""
    except Exception:
        pass


def validate(doc,method=None):
    try:
        for item in doc.required_items:            
            if item.required_qty:
                item.required_qty = math.ceil(item.required_qty)
    except Exception:
        pass