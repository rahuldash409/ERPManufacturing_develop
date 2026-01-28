import frappe
from erpnext.stock.stock_balance import get_ordered_qty, get_planned_qty
from frappe.query_builder.functions import IfNull, Sum


def get_available_qty(item_code, warehouse):
    available_qty = 0

    bin = frappe.qb.DocType("Bin")

    query = (
        frappe.qb.from_(bin)
        .select(
            bin.warehouse,
            IfNull(bin.projected_qty, 0).as_("projected_qty"),
            IfNull(bin.actual_qty, 0).as_("actual_qty"),
            IfNull(bin.ordered_qty, 0).as_("ordered_qty"),
            IfNull(bin.reserved_qty_for_production, 0).as_(
                "reserved_qty_for_production"
            ),
            IfNull(bin.planned_qty, 0).as_("planned_qty"),
        )
        .where((bin.item_code == item_code) & (bin.warehouse == warehouse))
        .groupby(bin.item_code, bin.warehouse)
    )

    records = query.run(as_dict=True)
    available_qty = sum([record.get("actual_qty") for record in records])
    return available_qty


def get_wo_remaining_qty(item_code, warehouse):
    wo_remaining_qty = 0
    wo = frappe.qb.DocType("Work Order")
    woi = frappe.qb.DocType("Work Order Item")

    query = (
        frappe.qb.from_(woi)
        .join(wo)
        .on(woi.parent == wo.name)
        .select(
            woi.parent.as_("work_order"),
            woi.name,
            woi.item_code,
            woi.source_warehouse.as_("warehouse"),
            IfNull(woi.required_qty, 0).as_("required_qty"),
            IfNull(woi.transferred_qty, 0).as_("transferred_qty"),
            IfNull(woi.consumed_qty, 0).as_("consumed_qty"),
            IfNull(woi.returned_qty, 0).as_("returned_qty"),
        )
        .where(
            (woi.item_code == item_code)
            & (woi.source_warehouse == warehouse)
            # & (wo.status != "Completed")
            & (wo.docstatus == 1)
        )
        .groupby(woi.item_code, woi.source_warehouse, wo.name)
    )

    records = query.run(as_dict=True)
    required_qty = sum([record.get("required_qty") for record in records])
    transferred_qty = sum([record.get("transferred_qty") for record in records])
    consumed_qty = sum([record.get("consumed_qty") for record in records])
    returned_qty = sum([record.get("returned_qty") for record in records])
    wo_remaining_qty = required_qty - consumed_qty
    # wo_remaining_qty = required_qty - (consumed_qty - returned_qty)

    return wo_remaining_qty


def get_item_available_qty(item_code, warehouse, required_qty=0):
    bin_actual_qty = get_available_qty(item_code, warehouse)
    # planned_qty = get_planned_qty(item_code, warehouse)
    ordered_qty = get_ordered_qty(item_code, warehouse)
    wo_remaining_qty = get_wo_remaining_qty(item_code, warehouse)
    available_qty = bin_actual_qty + ordered_qty - wo_remaining_qty
    formula = f"Required Qty - Bin Actual Qty + Ordered Qty - WO Remaining Qty : {required_qty} - {bin_actual_qty} + {ordered_qty} - {wo_remaining_qty} = {required_qty - available_qty}"
    log = f"""Item Code : {item_code}\nWarehouse : {warehouse}\n\nBin Actual Qty: {bin_actual_qty}\nOrdered Qty (PO Qty): {ordered_qty}\nWO Remaining Qty: {wo_remaining_qty}\nAvailable Qty: {available_qty}\nRequired Qty: {required_qty}\n\nFormula : {formula}"""
    frappe.log_error(f"Get Item Available Qty {item_code} {warehouse}", log)
    return available_qty
