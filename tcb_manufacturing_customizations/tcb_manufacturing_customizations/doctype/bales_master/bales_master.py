import traceback

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today


class BalesMaster(Document):
    pass


def get_available_batches_fifo(item_code, warehouse, required_qty):
    """
    Fetch batches in FIFO order (oldest first by creation date) with remaining qty.
    Remaining qty = Stock qty - Already consumed in Bales Ledger Entry
    """
    required_qty = flt(required_qty)

    # Get stock qty per batch from Stock Ledger Entry
    stock_batches = frappe.db.sql(
        """
        SELECT
            b.name as batch,
            b.custom_sub_batch as sub_batch,
            b.creation,
            SUM(sle.actual_qty) as stock_qty
        FROM `tabBatch` b
        INNER JOIN `tabSerial and Batch Entry` sbe ON sbe.batch_no = b.name
        INNER JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sbe.parent
        WHERE sle.item_code = %s
          AND sle.warehouse = %s
          AND sle.is_cancelled = 0
        GROUP BY b.name
        HAVING stock_qty > 0
        ORDER BY b.creation ASC
    """,
        (item_code, warehouse),
        as_dict=True,
    )

    # Get already consumed qty from Bales Ledger Entry
    consumed = frappe.db.sql(
        """
        SELECT batch, SUM(qty_consumed) as consumed
        FROM `tabBales Ledger Entry`
        WHERE item_code = %s AND warehouse = %s
        GROUP BY batch
    """,
        (item_code, warehouse),
        as_dict=True,
    )

    consumed_map = {c.batch: flt(c.consumed) for c in consumed}

    # Calculate remaining and fill batches
    result = []
    remaining_required = required_qty

    for batch in stock_batches:
        consumed_qty = consumed_map.get(batch.batch, 0)
        available = flt(batch.stock_qty) - consumed_qty

        if available <= 0:
            continue

        qty_to_take = min(available, remaining_required)
        result.append(
            {
                "batch": batch.batch,
                "sub_batch": batch.sub_batch,
                "qty_taken": qty_to_take,
            }
        )

        remaining_required -= qty_to_take
        if remaining_required <= 0:
            break

    return result


def create_bales_ledger_entry(bales_name, item_code, warehouse, batch_data):
    """Create a Bales Ledger Entry for batch consumption tracking"""
    ledger_entry = frappe.new_doc("Bales Ledger Entry")
    ledger_entry.bales = bales_name
    ledger_entry.item_code = item_code
    ledger_entry.warehouse = warehouse
    ledger_entry.batch = batch_data.get("batch")
    ledger_entry.sub_batch = batch_data.get("sub_batch")
    ledger_entry.qty_consumed = batch_data.get("qty_taken")
    ledger_entry.posting_date = today()
    ledger_entry.insert(ignore_permissions=True)


@frappe.whitelist()
def auto_fetch_batch_data(item_code, warehouse, qty):
    response = {"success": False, "msg": "Something went wrong", "data": {}}
    try:
        # from erpnext.stock.doctype.batch.batch import get_batch_qty
        from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import (
            get_auto_batch_nos,
        )

        kwargs = dict(
            item_code=item_code, warehouse=warehouse, qty=qty, based_on="FIFO"
        )
        kwargs = frappe._dict(kwargs)
        batch_nos = get_auto_batch_nos(kwargs)
        frappe.log_error("Batch Nos", batch_nos)
        batch_no_data = {}
        if len(batch_nos) > 0:
            batch_no_data = batch_nos[-1]
            if batch_no_data.get("qty") < flt(qty):
                response["msg"] = "No batch found with the enough qty"
            else:
                batch_no = batch_no_data.get("batch_no")
                batch_no_data["sub_batch"] = frappe.db.get_value(
                    "Batch", batch_no, "custom_sub_batch"
                )
                response["success"] = True
                response["msg"] = "Batch auto fetched!"
                response["data"] = batch_no_data
        else:
            response["msg"] = "No batch found"

        return response

    except Exception:
        frappe.log_error("Error auto_fetch_batch_data", traceback.format_exc())
        return response


@frappe.whitelist()
def create_bales(item_code, warehouse, qty, bales_source=None):
    """Create a Bales document from Bales Master Item row with FIFO batch allocation"""
    response = {"success": False, "msg": "Something went wrong", "bales_id": None}
    try:
        if not item_code or not warehouse or not qty:
            response["msg"] = "Item Code, Warehouse and Qty are required"
            return response

        qty = flt(qty)

        # 1. Fetch available batches in FIFO order
        batches = get_available_batches_fifo(item_code, warehouse, qty)

        if not batches:
            response["msg"] = "No batches available with sufficient quantity"
            return response

        # Calculate total qty available from batches
        total_available = sum(b["qty_taken"] for b in batches)
        if total_available < qty:
            response["msg"] = f"Insufficient batch quantity. Required: {qty}, Available: {total_available}"
            return response

        # 2. Create Bales document
        bales_doc = frappe.new_doc("Bales")
        bales_doc.item = item_code
        bales_doc.warehouse = warehouse
        bales_doc.bale_qty = qty
        bales_doc.bales_source = bales_source
        bales_doc.source_document_type = "Bales Master"

        # 3. Fill batches_used table
        for batch_data in batches:
            bales_doc.append(
                "batches_used",
                {
                    "batch": batch_data["batch"],
                    "sub_batch": batch_data["sub_batch"],
                    "qty_taken": batch_data["qty_taken"],
                    "item": item_code,
                    "warehouse": warehouse,
                },
            )

        bales_doc.insert()

        # 4. Create Bales Ledger Entries for each batch consumed
        for batch_data in batches:
            create_bales_ledger_entry(bales_doc.name, item_code, warehouse, batch_data)

        response["success"] = True
        response["msg"] = f"Bales {bales_doc.name} created successfully"
        response["bales_id"] = bales_doc.name

        return response

    except Exception:
        frappe.log_error("Error create_bales", traceback.format_exc())
        return response
