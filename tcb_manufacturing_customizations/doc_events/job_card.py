import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# @frappe.whitelist()
# def create_multiple_qc():
#     settings = frappe.get_single("Manufacturing Settings")
#     if settings.allow_multiple_qc:
#         create_custom_fields({
#             "Job Card":[
#             dict(fieldname="create_qcs",label="Create Quality Inspection",fieldtype="Button",insert_after="quality_inspection"),
#             dict(fieldname="quality_inspections",label="Quality Inspections",fieldtype="Table",options="Quality Inspections",insert_after="quality_inspection")
#             ]
#         })


# @frappe.whitelist()
# def create_qc(doc):
#     jc = frappe.get_doc("Job Card",doc)
#     qc = frappe.get_doc("Quality Inspection",inspection_type="In Process",reference_type="Job Card",reference_name=doc,item_code=jc.production_item)
#     qc.save()
#     return qc.name

# BEFORE SUBMIT, DO NOT LET SUBMIT IF PRODUCTION QTY DOESNT EXIST
def checkprodqty(doc,method=None):
    if not doc.custom_material_consumed_after_deducting_wastage:
        frappe.throw("Cannot Move Forward. Material Production After deducting wastage is 0")


@frappe.whitelist()
def get_quality_inspections(jc):
    jcard = frappe.get_doc("Job Card",jc)
    quality_inspections = frappe.get_all("Quality Inspection",{"reference_type":"Job Card","reference_name":jcard.name,"docstatus":1},pluck="name")
    existing= {row.quality_inspection for row in jcard.custom_quality_inspections}
    
    flag = False
    for qc in quality_inspections:
        if qc not in existing:
            jcard.append("custom_quality_inspections", {
                "quality_inspection": qc
            })
            flag = True

    if flag:
        jcard.flags.ignore_on_update = True
        jcard.quality_inspection = ""
        jcard.save()
        frappe.db.commit()
    return jcard.name

def validate_jc(doc,method=None):
    qc = frappe.get_list("Quality Inspection",{"custom_on_hold1":1,"docstatus":0,"reference_name":doc.name},pluck="name")
    if qc:
        frappe.throw(f"Quality Inspection <b>{qc}</b> is on Hold, cannot proceed further.")

    # Validate Bales Plan if present
    validate_bales_plan(doc)


def validate_bales_plan(doc):
    """
    Validate Bales Plan entries:
    1. Total batch_qty_used should not exceed available qty in packaging materials
    2. Each batch's usage should not exceed its available qty
    """
    from frappe.utils import flt

    if not hasattr(doc, 'custom_bales_plan') or not doc.custom_bales_plan:
        return

    if not hasattr(doc, 'custom_packaging_materials') or not doc.custom_packaging_materials:
        return

    # Get available qty per batch from packaging materials (only segregated items)
    available_by_batch = {}
    for pm in doc.custom_packaging_materials:
        # Check if item belongs to segregated group
        item_group = frappe.db.get_value("Item", pm.item_code, "item_group")
        if item_group and item_group.lower() == "segregated ad*star bags":
            batch_key = (pm.item_code, pm.batch_no or "")
            if batch_key not in available_by_batch:
                available_by_batch[batch_key] = 0
            available_by_batch[batch_key] += flt(pm.qty)

    # Calculate used qty per batch from bales plan
    used_by_batch = {}
    total_planned = 0
    unique_bales = set()

    for entry in doc.custom_bales_plan:
        batch_key = (entry.packaging_item, entry.batch_no or "")
        if batch_key not in used_by_batch:
            used_by_batch[batch_key] = 0
        used_by_batch[batch_key] += flt(entry.batch_qty_used)

        # Calculate unique bales total qty
        if entry.bale_number and entry.bale_number not in unique_bales:
            unique_bales.add(entry.bale_number)
            total_planned += flt(entry.bale_qty)

    # Validate batch usage
    for batch_key, used_qty in used_by_batch.items():
        available_qty = available_by_batch.get(batch_key, 0)
        if used_qty > available_qty:
            item_code, batch_no = batch_key
            frappe.throw(
                f"Bales Plan Error: Batch {batch_no} of {item_code} uses {used_qty} qty "
                f"but only {available_qty} is available in Packaging Materials."
            )

    # Update total fields
    total_available = sum(available_by_batch.values())
    doc.custom_total_segregated_qty = total_available
    doc.custom_total_bales_qty_planned = total_planned



def cancel_jc(doc,method=None):
    if doc.custom_material_consumption:
        doc.custom_material_consumption = []
    # frappe.db.set_value("Job Card",doc.name,doc.custom_total_material_consumed,0.0)
    # frappe.db.set_value("Job Card",doc.name,doc.custom_material_consumed_after_deducting_wastage,0.0)
    # frappe.db.set_value("Job Card",doc.name,doc.custom_total_material_wasted,0)
    # frappe.db.set_value("Job Card",doc.name,doc.custom_process_loss,0)
    # frappe.db.set_value("Job Card",doc.name,doc.custom_total_material_wasted_lbs,0)   
    doc.custom_total_material_consumed = 0.0
    doc.custom_material_consumed_after_deducting_wastage = 0.0
    doc.custom_total_material_wast = 0.0
    doc.custom_process_lo = 0.0
    doc.custom_total_material_wasted_l = 0.0
    if doc.time_logs:
        doc.time_logs = []
    
    
    
    
@frappe.whitelist()
def get_fg_to_rm_ratio(bom_no):
    if not bom_no:
        return [0, 0, 0]

    bom = frappe.get_doc("BOM", bom_no)

    fg_qty = bom.quantity or 0
    mb_qty = 0
    sl_pa = 0
    sl_va = 0

    for row in bom.items:
        item_name = (row.item_name or "").lower()

        if "main body" in item_name:
            mb_qty += row.qty or 0

        if "patch" in item_name:
            sl_pa += row.qty or 0

        if "valve" in item_name:
            sl_va += row.qty or 0

    def safe_ratio(fg, rm):
        return round(fg / rm, 2) if rm else 0

    mb_ratio = safe_ratio(fg_qty, mb_qty)
    sl_pa_ratio = safe_ratio(fg_qty, sl_pa)
    sl_va_ratio = safe_ratio(fg_qty, sl_va)

    return [mb_ratio, sl_pa_ratio, sl_va_ratio]




@frappe.whitelist()
def get_main_body_ratio(bom_no):
    if not bom_no:
        return 0
    
    bom = frappe.get_doc("BOM", bom_no)
    fg_qty = bom.quantity or 0
    mb_qty = 0
    
    for row in bom.items:
        item_name = (row.item_name or "").lower()
        if "main body" in item_name or "main-body" in item_name:
            mb_qty += row.qty or 0
    
    return round(fg_qty / mb_qty, 4) if mb_qty else 0