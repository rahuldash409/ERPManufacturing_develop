import frappe
from frappe.utils import flt
from erpnext.manufacturing.doctype.work_order import work_order
import json

class CustomWorkOrder(work_order.WorkOrder):
    def create_job_card(self):
        pass

def override_make_stock_entry(doc,method):
    from erpnext.manufacturing.doctype.work_order import work_order
    work_order.make_stock_entry = make_stock_entry

@frappe.whitelist()
def make_stock_entry(work_order_id, purpose, qty=None, target_warehouse=None, jc_list=None,mat_entry_type=None,raw_materials=None,wastage=None,wastage_items=None):
    work_order = frappe.get_doc("Work Order", work_order_id)
    
    if not frappe.db.get_value("Warehouse", work_order.wip_warehouse, "is_group"):
        wip_warehouse = work_order.wip_warehouse
    else:
        wip_warehouse = None

    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.purpose = purpose
    stock_entry.work_order = work_order_id
    stock_entry.company = work_order.company
    stock_entry.from_bom = 1
    stock_entry.bom_no = work_order.bom_no
    stock_entry.use_multi_level_bom = work_order.use_multi_level_bom
    stock_entry.stock_entry_type = mat_entry_type
    stock_entry.custom_job_card_reference = jc_list
    
    
    raw_mats = frappe.parse_json(raw_materials) or {}
    wastage_item = frappe.parse_json(wastage_items) or {}
    
    if wastage_item:
        for rows in wastage_item:
            stock_entry.append("custom_wastage_from_job_card",{
                "item":rows.get("item_code"),
                "wastage_qty":rows.get("stock_qty")
            })
    
    for item_code,rows in raw_mats.items():
        for row in rows:
            stock_entry.append("custom_quick_entry", {
                "source_warehouse":row.get("from_warehouse") or "",
                "item": row.get("item"),
                "qty": float(row.get("qty")),
                "sub_batch": row.get("sub_batch") or "", 
                "batch": row.get("batch") or "",
                "machine_consumption":row.get("machine_consumption") or 0,
                "slitec_roll_cut_lengths":row.get("roll_cutlengths") or "",
                "produced_good_qty":row.get("manufactured_bags") or "",
                "bale":row.get("bale_n") or ""
            })

    # Accept 0 qty as well
    stock_entry.fg_completed_qty = (
        qty if qty is not None else (flt(work_order.qty) - flt(work_order.produced_qty))
    )

    if work_order.bom_no:
        stock_entry.inspection_required = frappe.db.get_value(
            "BOM", work_order.bom_no, "inspection_required"
        )

    if purpose == "Material Transfer for Manufacture":
        stock_entry.to_warehouse = wip_warehouse
        stock_entry.project = work_order.project
    else:
        stock_entry.from_warehouse = wip_warehouse
        stock_entry.to_warehouse = work_order.fg_warehouse

    if purpose == "Disassemble":
        stock_entry.from_warehouse = work_order.fg_warehouse
        stock_entry.to_warehouse = target_warehouse or work_order.source_warehouse

    stock_entry.set_stock_entry_type()
    stock_entry.get_items()

    if purpose != "Disassemble":
        stock_entry.set_serial_no_batch_for_finished_good()

    return stock_entry.as_dict()

def validate(doc,method=None):
    if doc.custom_job_card_reference:
        jc = doc.custom_job_card_reference.split(",")
        for card in jc:
            job_card = frappe.get_doc("Job Card",card)
            if not job_card.custom_stock_entry_reference:
                frappe.db.set_value("Job Card",card,"custom_stock_entry_reference",doc.name)

def on_trash(doc,method=None):
    if doc.custom_job_card_reference:
        jc = doc.custom_job_card_reference.split(",")
        for card in jc:
            job_card = frappe.get_doc("Job Card",card)
            if job_card.custom_stock_entry_reference:
                frappe.db.set_value("Job Card",card,"custom_stock_entry_reference","")

def on_cancel(doc,method=None):
    try:
        if doc.custom_job_card_reference:
            jc = doc.custom_job_card_reference.split(",")
            for card in jc:
                job_card = frappe.get_doc("Job Card",card)
                if job_card.custom_stock_entry_reference:
                    frappe.db.set_value("Job Card",card,"custom_stock_entry_reference","")
    except Exception as e:
        frappe.throw(e)
   
   
   
#    On hold.. encountered error -> TypeError: expected string or bytes-like object 
    # try:
    #     if doc.job_card:
    #         job_cardd = frappe.get_doc("Job Card",doc.job_card)
    #         if job_cardd.custom_material_consumption and job_cardd.docstatus!=1:
    #             frappe.db.set_value("Job Card",doc.job_card,"custom_material_consumption",[])
    # except Exception as f:
    #     frappe.throw(f)