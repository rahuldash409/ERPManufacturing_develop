# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

"""
Bales Utility Functions

This module contains utility functions for creating and managing Bales
from Manufacturing and Import flows.

Flow 1: Manufacturing
- Job Card completion triggers Manufacture Stock Entry
- On Manufacture SE submit → Bales are created based on produced qty / custom_bale_qty

Flow 2: Import (Purchase Receipt)
- PR submit with items in "packaged ad*star bags" group → Bales created
"""

import frappe
from frappe import _
from frappe.utils import flt, cint


def create_bales_from_manufacture(stock_entry_doc, job_card_ref=None):
    """
    Create Bales when Manufacture Stock Entry is submitted.

    This function:
    1. Gets the Job Card linked to the Stock Entry
    2. Checks if Job Card has a Bales Plan - if yes, uses the plan
    3. If no plan, calculates number of bales based on qty / custom_bale_qty
    4. Creates Bales using packaging materials from Job Card

    Args:
        stock_entry_doc: Stock Entry document (Manufacture type)
        job_card_ref: Job Card name (passed from custom_job_card_reference field)

    Returns:
        list: Names of created bales
    """
    # Use passed job_card_ref or try to get from stock_entry_doc
    job_card_name = job_card_ref or getattr(stock_entry_doc, 'custom_job_card_reference', None)

    # Fallback to standard job_card field
    if not job_card_name:
        job_card_name = getattr(stock_entry_doc, 'job_card', None)

    if not job_card_name:
        frappe.log_error(
            f"Stock Entry {stock_entry_doc.name} has no job_card linked",
            "Bales Creation - No Job Card"
        )
        return []

    job_card = frappe.get_doc("Job Card", job_card_name)
    work_order_name = job_card.work_order

    # Check if Job Card has Bales Plan entries
    if hasattr(job_card, 'custom_bales_plan') and job_card.custom_bales_plan:
        # Use Bales Plan to create bales
        frappe.log_error(
            f"Using Bales Plan for SE {stock_entry_doc.name} - {len(job_card.custom_bales_plan)} plan entries",
            "Bales Creation - Using Plan"
        )
        return create_bales_from_plan(job_card, stock_entry_doc)

    # No Bales Plan - use auto-calculation based on qty / custom_bale_qty
    created_bales = []

    # Log for debugging
    frappe.log_error(
        f"Processing SE {stock_entry_doc.name} with {len(stock_entry_doc.items)} items (auto-calculation)",
        "Bales Creation - Start"
    )

    for item in stock_entry_doc.items:
        # Only process finished items
        if not item.is_finished_item:
            continue

        # Log finished item found
        frappe.log_error(
            f"Found finished item: {item.item_code}, qty: {item.qty}",
            "Bales Creation - Finished Item"
        )

        # Check if item has custom_bale_qty defined
        bale_qty = frappe.db.get_value("Item", item.item_code, "custom_bale_qty")

        if not bale_qty or flt(bale_qty) <= 0:
            # Skip items without bale qty defined
            frappe.log_error(
                f"Item {item.item_code} has no custom_bale_qty defined (value: {bale_qty})",
                "Bales Creation - No Bale Qty"
            )
            continue

        bale_qty = flt(bale_qty)
        produced_qty = flt(item.qty)

        if produced_qty <= 0:
            continue

        # Calculate number of full bales and remainder
        full_bales_count = int(produced_qty // bale_qty)
        remainder_qty = produced_qty % bale_qty

        # Get packaging materials from Job Card
        packaging_materials = get_packaging_materials_from_job_card(job_card)

        # Create full bales
        for i in range(full_bales_count):
            bale_name = create_single_bale(
                item_code=item.item_code,
                qty=bale_qty,
                warehouse=item.t_warehouse,
                packaging_materials=packaging_materials,
                stock_entry=stock_entry_doc.name,
                job_card=job_card.name,
                work_order=work_order_name,
                source="Manufacture",
                is_partial=False
            )
            if bale_name:
                created_bales.append(bale_name)

        # Create partial bale if remainder exists
        if remainder_qty > 0:
            bale_name = create_single_bale(
                item_code=item.item_code,
                qty=remainder_qty,
                warehouse=item.t_warehouse,
                packaging_materials=packaging_materials,
                stock_entry=stock_entry_doc.name,
                job_card=job_card.name,
                work_order=work_order_name,
                source="Manufacture",
                is_partial=True
            )
            if bale_name:
                created_bales.append(bale_name)

    return created_bales


def get_packaging_materials_from_job_card(job_card):
    """
    Get packaging materials from Job Card's custom_packaging_materials table.

    Args:
        job_card: Job Card document

    Returns:
        list: List of packaging material dictionaries
    """
    packaging_materials = []

    if hasattr(job_card, 'custom_packaging_materials') and job_card.custom_packaging_materials:
        for pm in job_card.custom_packaging_materials:
            packaging_materials.append(frappe._dict({
                "item_code": pm.item_code,
                "qty": flt(pm.qty),
                "batch_no": pm.batch_no,
                "sub_batch": pm.sub_batch or "",
                "warehouse": pm.warehouse,
                "stock_entry": pm.stock_entry
            }))

    return packaging_materials


def create_single_bale(item_code, qty, warehouse, packaging_materials,
                       stock_entry=None, job_card=None, work_order=None,
                       purchase_receipt=None, source="Manufacture", is_partial=False,
                       packed_items=None):
    """
    Create a single Bale document.

    Args:
        item_code: Item code for the bale
        qty: Quantity in the bale
        warehouse: Target warehouse
        packaging_materials: List of packaging materials with batch info (raw materials)
        stock_entry: Stock Entry name (for manufacture)
        job_card: Job Card name (for manufacture)
        work_order: Work Order name (for manufacture)
        purchase_receipt: Purchase Receipt name (for import)
        source: "Manufacture" or "Import"
        is_partial: Whether this is a partial bale
        packed_items: List of finished goods items with batch info (for DN dispatch)

    Returns:
        str: Created bale name or None if failed
    """
    try:
        # Get or create Bales Source
        bales_source = get_bales_source(source)

        if not bales_source:
            frappe.log_error(
                f"Bales Source not found for: {source}",
                "Bales Creation Error"
            )
            return None

        # Create Bale document
        bale = frappe.new_doc("Bales")
        bale.item = item_code
        bale.warehouse = warehouse
        bale.bale_qty = qty
        bale.bales_source = bales_source
        bale.posting_date = frappe.utils.today()
        bale.is_partial_bale = 1 if is_partial else 0

        # Source document linking
        if source == "Manufacture":
            bale.source_document_type = "Stock Entry"
            bale.source_document = stock_entry
            bale.material_consumption_entry = stock_entry
            bale.job_card = job_card
            bale.work_order = work_order
            # Set initial status for manufacture
            bale.bales_status = "Packed In House"
        elif source == "Import":
            bale.source_document_type = "Purchase Receipt"
            bale.source_document = purchase_receipt
            # Set initial status for import
            bale.bales_status = "Packed Import"

        # Add batches from packaging materials
        # For Manufacturing flow: batches from Job Card's custom_packaging_materials
        # For Import flow: batches from Purchase Receipt's Serial and Batch Bundle
        if packaging_materials:
            for pm in packaging_materials:
                if pm.get("batch_no"):
                    # For Manufacturing, we skip batch reuse validation as same batches
                    # are used across multiple bales from same Job Card
                    # For Import, validate batch not already used
                    if source == "Import":
                        if is_batch_used_in_bale(pm.get("batch_no"), pm.get("item_code")):
                            frappe.throw(_(
                                "Batch {0} of Item {1} is already used in another Bale. "
                                "Cannot reuse batch."
                            ).format(pm.get("batch_no"), pm.get("item_code")))

                    bale.append("batches_used", {
                        "item": pm.get("item_code"),
                        "batch": pm.get("batch_no"),
                        "sub_batch": pm.get("sub_batch", ""),
                        "qty_taken": flt(pm.get("qty")),
                        "warehouse": pm.get("warehouse") or warehouse
                    })

        # Add packed items (finished goods with batches) for Delivery Note dispatch
        if packed_items:
            for pi in packed_items:
                bale.append("packed_items", {
                    "item_code": pi.get("item_code"),
                    "item_name": pi.get("item_name", ""),
                    "qty": flt(pi.get("qty")),
                    "batch_no": pi.get("batch_no"),
                    "sub_batch": pi.get("sub_batch", ""),
                    "warehouse": pi.get("warehouse") or warehouse
                })

        bale.insert()
        bale.submit()

        return bale.name

    except Exception as e:
        frappe.log_error(
            f"Error creating bale for {item_code}: {str(e)}",
            "Bales Creation Error"
        )
        return None


def is_batch_used_in_bale(batch_no, item_code):
    """
    Check if a batch is already used in any submitted Bale.

    Args:
        batch_no: Batch number
        item_code: Item code

    Returns:
        bool: True if batch is already used
    """
    if not batch_no:
        return False

    exists = frappe.db.exists("Bales Ledger Entry", {
        "batch": batch_no,
        "item_code": item_code
    })
    return bool(exists)


def get_bales_source(source_type):
    """
    Get or create Bales Source record.

    Args:
        source_type: "Manufacture" or "Import"

    Returns:
        str: Bales Source name or None
    """
    source_map = {
        "Manufacture": ["Manufacture", "Manufacturing", "Manufactured"],
        "Import": ["Import", "Imported"]
    }

    for source_name in source_map.get(source_type, []):
        if frappe.db.exists("Bales Source", source_name):
            return source_name

    # Create if not exists
    try:
        source = frappe.new_doc("Bales Source")
        source.bales_source = source_type
        source.insert(ignore_permissions=True)
        return source.name
    except Exception:
        return None


def create_bales_from_purchase_receipt(purchase_receipt_doc):
    """
    Create Bales when Purchase Receipt is submitted.
    Only for items with Item Group = "packaged ad*star bags"

    Args:
        purchase_receipt_doc: Purchase Receipt document

    Returns:
        list: Names of created bales
    """
    created_bales = []

    for item in purchase_receipt_doc.items:
        # Check item group - must be "packaged ad*star bags"
        item_group = frappe.db.get_value("Item", item.item_code, "item_group")

        if not item_group or item_group.lower() != "packaged ad*star bags":
            continue

        # Get custom_bale_qty
        bale_qty = frappe.db.get_value("Item", item.item_code, "custom_bale_qty")

        if not bale_qty or flt(bale_qty) <= 0:
            frappe.log_error(
                f"Item {item.item_code} does not have valid custom_bale_qty",
                "Bales Creation Warning"
            )
            continue

        bale_qty = flt(bale_qty)
        received_qty = flt(item.qty)

        if received_qty <= 0:
            continue

        # Get batches from Serial and Batch Bundle
        packaging_materials = get_batches_from_pr_item(item)

        # Calculate bales
        full_bales_count = int(received_qty // bale_qty)
        remainder_qty = received_qty % bale_qty

        # Create full bales
        for i in range(full_bales_count):
            bale_name = create_single_bale(
                item_code=item.item_code,
                qty=bale_qty,
                warehouse=item.warehouse,
                packaging_materials=packaging_materials,
                purchase_receipt=purchase_receipt_doc.name,
                source="Import",
                is_partial=False
            )
            if bale_name:
                created_bales.append(bale_name)

        # Create partial bale
        if remainder_qty > 0:
            bale_name = create_single_bale(
                item_code=item.item_code,
                qty=remainder_qty,
                warehouse=item.warehouse,
                packaging_materials=packaging_materials,
                purchase_receipt=purchase_receipt_doc.name,
                source="Import",
                is_partial=True
            )
            if bale_name:
                created_bales.append(bale_name)

    return created_bales


def get_batches_from_pr_item(pr_item):
    """
    Get batch information from Purchase Receipt item's Serial and Batch Bundle.

    Args:
        pr_item: Purchase Receipt Item row

    Returns:
        list: List of batch dictionaries
    """
    packaging_materials = []

    if not pr_item.serial_and_batch_bundle:
        return packaging_materials

    # Get entries from Serial and Batch Bundle
    bundle_entries = frappe.get_all(
        "Serial and Batch Entry",
        filters={"parent": pr_item.serial_and_batch_bundle},
        fields=["batch_no", "qty", "warehouse"]
    )

    for entry in bundle_entries:
        # Get sub_batch from Batch if exists
        sub_batch = ""
        if entry.batch_no:
            sub_batch = frappe.db.get_value("Batch", entry.batch_no, "custom_sub_batch") or ""

        packaging_materials.append(frappe._dict({
            "item_code": pr_item.item_code,
            "qty": flt(entry.qty),
            "batch_no": entry.batch_no,
            "sub_batch": sub_batch,
            "warehouse": entry.warehouse or pr_item.warehouse
        }))

    return packaging_materials


def cancel_bales_from_stock_entry(stock_entry_doc):
    """
    Cancel Bales when Manufacture Stock Entry is cancelled.

    Args:
        stock_entry_doc: Stock Entry document
    """
    # Get all bales linked to this Stock Entry
    bales_list = frappe.get_all(
        "Bales",
        filters={
            "source_document_type": "Stock Entry",
            "source_document": stock_entry_doc.name,
            "docstatus": 1
        },
        pluck="name"
    )

    if not bales_list:
        return

    # Check for dispatched bales
    dispatched_bales = []
    for bale_name in bales_list:
        status = frappe.db.get_value("Bales", bale_name, "bales_status")
        if status == "Dispatched":
            dispatched_bales.append(bale_name)

    if dispatched_bales:
        frappe.throw(_(
            "Cannot cancel Stock Entry. The following Bales have been dispatched: {0}. "
            "Please cancel the linked Delivery Note(s) first."
        ).format(", ".join(dispatched_bales)))

    # Set flag to allow cancellation
    frappe.flags.stock_entry_bale_cancel = True

    try:
        for bale_name in bales_list:
            bale = frappe.get_doc("Bales", bale_name)
            bale.flags.ignore_links = True
            bale.cancel()

        if bales_list:
            frappe.msgprint(
                _("Cancelled {0} Bales linked to this Stock Entry").format(len(bales_list)),
                indicator="green",
                alert=True
            )
    finally:
        frappe.flags.stock_entry_bale_cancel = False


def cancel_bales_from_purchase_receipt(purchase_receipt_doc):
    """
    Cancel Bales when Purchase Receipt is cancelled.

    Args:
        purchase_receipt_doc: Purchase Receipt document
    """
    # Get all bales linked to this Purchase Receipt
    bales_list = frappe.get_all(
        "Bales",
        filters={
            "source_document_type": "Purchase Receipt",
            "source_document": purchase_receipt_doc.name,
            "docstatus": 1
        },
        pluck="name"
    )

    if not bales_list:
        return

    # Check for dispatched bales
    dispatched_bales = []
    for bale_name in bales_list:
        status = frappe.db.get_value("Bales", bale_name, "bales_status")
        if status == "Dispatched":
            dispatched_bales.append(bale_name)

    if dispatched_bales:
        frappe.throw(_(
            "Cannot cancel Purchase Receipt. The following Bales have been dispatched: {0}. "
            "Please cancel the linked Delivery Note(s) first."
        ).format(", ".join(dispatched_bales)))

    # Set flag to allow cancellation
    frappe.flags.purchase_receipt_bale_cancel = True

    try:
        for bale_name in bales_list:
            bale = frappe.get_doc("Bales", bale_name)
            bale.cancel()

        if bales_list:
            frappe.msgprint(
                _("Cancelled {0} Bales linked to this Purchase Receipt").format(len(bales_list)),
                indicator="green",
                alert=True
            )
    finally:
        frappe.flags.purchase_receipt_bale_cancel = False


def populate_job_card_packaging_materials(stock_entry_doc, job_card_ref=None):
    """
    Populate Job Card's packaging materials table when Material Transfer
    for Manufacture Stock Entry is submitted.

    Only items belonging to "segregated ad*star bags" group are added
    to the packaging materials table.

    Args:
        stock_entry_doc: Stock Entry document (Material Transfer for Manufacture)
        job_card_ref: Job Card name (passed from custom_job_card_reference field)
    """
    # Use passed job_card_ref or try to get from stock_entry_doc
    job_card_name = job_card_ref or getattr(stock_entry_doc, 'custom_job_card_reference', None)

    # Fallback to standard job_card field
    if not job_card_name:
        job_card_name = getattr(stock_entry_doc, 'job_card', None)

    if not job_card_name:
        return

    job_card = frappe.get_doc("Job Card", job_card_name)

    items_added = False
    for item in stock_entry_doc.items:
        # Only add items belonging to "segregated ad*star bags" group
        item_group = frappe.db.get_value("Item", item.item_code, "item_group")
        if not item_group or item_group.lower() != "segregated ad*star bags":
            continue

        # Get batch info
        batch_no = item.batch_no or ""
        sub_batch = ""

        if batch_no:
            sub_batch = frappe.db.get_value("Batch", batch_no, "custom_sub_batch") or ""

        # Append to packaging materials table
        job_card.append("custom_packaging_materials", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": flt(item.qty),
            "uom": item.uom,
            "batch_no": batch_no,
            "sub_batch": sub_batch,
            "stock_entry": stock_entry_doc.name,
            "warehouse": item.s_warehouse or item.t_warehouse
        })
        items_added = True

    if items_added:
        job_card.save(ignore_permissions=True)


def clear_job_card_packaging_materials(stock_entry_doc, job_card_ref=None):
    """
    Clear Job Card's packaging materials when Material Transfer
    for Manufacture Stock Entry is cancelled.

    Args:
        stock_entry_doc: Stock Entry document
        job_card_ref: Job Card name (passed from custom_job_card_reference field)
    """
    # Use passed job_card_ref or try to get from stock_entry_doc
    job_card_name = job_card_ref or getattr(
        stock_entry_doc, 'custom_job_card_reference', None
    )

    # Fallback to standard job_card field
    if not job_card_name:
        job_card_name = getattr(stock_entry_doc, 'job_card', None)

    if not job_card_name:
        return

    # Remove entries linked to this Stock Entry
    frappe.db.delete(
        "Job Card Packaging Material",
        {
            "parent": job_card_name,
            "stock_entry": stock_entry_doc.name
        }
    )


@frappe.whitelist()
def get_available_batches_for_bales(item_code, warehouse=None):
    """
    Get batches that are available for Bales creation.
    Returns batches that:
    1. Have stock available
    2. Are NOT already used in any submitted Bale

    Args:
        item_code: Item code to get batches for
        warehouse: Optional warehouse filter

    Returns:
        list: List of available batch dictionaries
    """
    if not item_code:
        return []

    # Check if item belongs to "segregated ad*star bags" group
    item_group = frappe.db.get_value("Item", item_code, "item_group")
    if not item_group or item_group.lower() != "segregated ad*star bags":
        return []

    # Get batches already used in submitted Bales
    used_batches = frappe.get_all(
        "Bales Ledger Entry",
        filters={"item_code": item_code},
        pluck="batch"
    )

    # Get all batches with stock for this item
    filters = {"item": item_code, "batch_qty": [">", 0]}

    batches = frappe.get_all(
        "Batch",
        filters=filters,
        fields=["name", "batch_qty", "custom_sub_batch", "expiry_date"],
        order_by="creation asc"
    )

    # Filter out used batches and get actual stock qty
    available_batches = []
    for batch in batches:
        if batch.name in used_batches:
            continue

        # Get actual stock qty from bin if warehouse specified
        if warehouse:
            from erpnext.stock.doctype.batch.batch import get_batch_qty
            actual_qty = get_batch_qty(batch.name, warehouse, item_code)
            if actual_qty <= 0:
                continue
            batch["actual_qty"] = actual_qty
        else:
            batch["actual_qty"] = batch.batch_qty

        available_batches.append({
            "batch_no": batch.name,
            "sub_batch": batch.custom_sub_batch or "",
            "qty": batch.actual_qty,
            "expiry_date": batch.expiry_date
        })

    return available_batches


@frappe.whitelist()
def is_segregated_item(item_code):
    """
    Check if item belongs to 'segregated ad*star bags' item group.

    Args:
        item_code: Item code to check

    Returns:
        bool: True if item is in segregated group
    """
    if not item_code:
        return False

    item_group = frappe.db.get_value("Item", item_code, "item_group")
    return item_group and item_group.lower() == "segregated ad*star bags"


@frappe.whitelist()
def get_batch_query_for_packaging(
    doctype, txt, searchfield, start, page_len, filters
):
    """
    Query function for batch selection in Job Card Packaging Material.
    Returns batches that are NOT already used in any submitted Bale.

    Args:
        filters: Should contain 'item_code' and optionally 'warehouse'

    Returns:
        list: List of batch tuples for link field
    """
    item_code = filters.get("item_code")
    warehouse = filters.get("warehouse")

    if not item_code:
        return []

    # Get batches already used in submitted Bales
    used_batches = frappe.get_all(
        "Bales Ledger Entry",
        filters={"item_code": item_code},
        pluck="batch"
    )

    # Build conditions
    conditions = ["b.item = %(item_code)s"]
    values = {
        "item_code": item_code,
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    }

    if txt:
        conditions.append(
            "(b.name LIKE %(txt)s OR b.custom_sub_batch LIKE %(txt)s)"
        )

    if used_batches:
        conditions.append("b.name NOT IN %(used_batches)s")
        values["used_batches"] = used_batches

    # If warehouse specified, filter batches with stock in that warehouse
    if warehouse:
        query = """
            SELECT DISTINCT b.name, b.custom_sub_batch, b.batch_qty
            FROM `tabBatch` b
            INNER JOIN `tabStock Ledger Entry` sle ON sle.batch_no = b.name
            WHERE {conditions}
                AND sle.warehouse = %(warehouse)s
                AND sle.is_cancelled = 0
            GROUP BY b.name
            HAVING SUM(sle.actual_qty) > 0
            ORDER BY b.creation ASC
            LIMIT %(start)s, %(page_len)s
        """.format(conditions=" AND ".join(conditions))
        values["warehouse"] = warehouse
    else:
        query = """
            SELECT b.name, b.custom_sub_batch, b.batch_qty
            FROM `tabBatch` b
            WHERE {conditions}
                AND b.batch_qty > 0
            ORDER BY b.creation ASC
            LIMIT %(start)s, %(page_len)s
        """.format(conditions=" AND ".join(conditions))

    return frappe.db.sql(query, values)


# ===========================================================================
# BALES PLAN FEATURE - API Functions
# ===========================================================================

@frappe.whitelist()
def is_packaged_adstar_item(item_code):
    """
    Check if item belongs to 'packaged ad*star bags' item group.

    Args:
        item_code: Item code to check

    Returns:
        bool: True if item is in packaged ad*star bags group
    """
    if not item_code:
        return False

    item_group = frappe.db.get_value("Item", item_code, "item_group")
    return item_group and item_group.lower() == "packaged ad*star bags"


@frappe.whitelist()
def get_segregated_packaging_qty(job_card):
    """
    Get total qty from packaging materials that belong to 'segregated ad*star bags' group.

    Args:
        job_card: Job Card name

    Returns:
        dict: {total_qty: float, items: list}
    """
    if not job_card:
        return {"total_qty": 0, "items": []}

    job_card_doc = frappe.get_doc("Job Card", job_card)

    if not hasattr(job_card_doc, 'custom_packaging_materials') or not job_card_doc.custom_packaging_materials:
        return {"total_qty": 0, "items": []}

    total_qty = 0
    items = []

    for pm in job_card_doc.custom_packaging_materials:
        # Check if item belongs to segregated group
        item_group = frappe.db.get_value("Item", pm.item_code, "item_group")
        if item_group and item_group.lower() == "segregated ad*star bags":
            total_qty += flt(pm.qty)
            items.append({
                "item_code": pm.item_code,
                "qty": flt(pm.qty),
                "batch_no": pm.batch_no,
                "sub_batch": pm.sub_batch,
                "warehouse": pm.warehouse
            })

    return {"total_qty": total_qty, "items": items}


@frappe.whitelist()
def generate_bales_plan(job_card, bale_qty):
    """
    Generate Bales Plan with FIFO batch split algorithm.

    Args:
        job_card: Job Card name
        bale_qty: Quantity per bale

    Returns:
        dict: {success: bool, message: str, bales_count: int}
    """
    bale_qty = flt(bale_qty)

    if bale_qty <= 0:
        return {"success": False, "error": "Invalid bale qty"}

    job_card_doc = frappe.get_doc("Job Card", job_card)

    # Get segregated packaging materials
    segregated_data = get_segregated_packaging_qty(job_card)

    if segregated_data["total_qty"] <= 0:
        return {"success": False, "error": "No segregated packaging materials found"}

    total_available = segregated_data["total_qty"]
    items = segregated_data["items"]

    # Sort items by batch creation date (FIFO)
    # Get batch creation dates
    for item in items:
        if item["batch_no"]:
            batch_creation = frappe.db.get_value("Batch", item["batch_no"], "creation")
            item["batch_creation"] = batch_creation or ""
        else:
            item["batch_creation"] = ""

    items.sort(key=lambda x: x.get("batch_creation", ""))

    # Calculate number of bales
    full_bales_count = int(total_available // bale_qty)
    remainder_qty = total_available % bale_qty

    # Clear existing bales plan
    job_card_doc.set("custom_bales_plan", [])

    # Generate plan entries with FIFO batch split
    bale_number = 1
    remaining_in_current_bale = bale_qty
    current_item_idx = 0
    remaining_in_current_item = flt(items[0]["qty"]) if items else 0

    production_item = job_card_doc.production_item
    production_item_name = frappe.db.get_value("Item", production_item, "item_name")

    while current_item_idx < len(items):
        current_item = items[current_item_idx]

        # How much can we take from this item for current bale?
        qty_to_take = min(remaining_in_current_item, remaining_in_current_bale)

        if qty_to_take > 0:
            # Get sub_batch from batch
            sub_batch = ""
            if current_item["batch_no"]:
                sub_batch = frappe.db.get_value(
                    "Batch", current_item["batch_no"], "custom_sub_batch"
                ) or ""

            # Add plan entry
            job_card_doc.append("custom_bales_plan", {
                "bale_number": bale_number,
                "packed_item": production_item,
                "item_name": production_item_name,
                "bale_qty": bale_qty if bale_number <= full_bales_count else remainder_qty,
                "packaging_item": current_item["item_code"],
                "batch_no": current_item["batch_no"],
                "sub_batch": sub_batch,
                "batch_qty_used": qty_to_take
            })

            remaining_in_current_item -= qty_to_take
            remaining_in_current_bale -= qty_to_take

        # Move to next item if current is exhausted
        if remaining_in_current_item <= 0:
            current_item_idx += 1
            if current_item_idx < len(items):
                remaining_in_current_item = flt(items[current_item_idx]["qty"])

        # Move to next bale if current is full
        if remaining_in_current_bale <= 0:
            bale_number += 1

            # Check if we've created all bales (full + partial)
            if bale_number > full_bales_count:
                if remainder_qty > 0:
                    remaining_in_current_bale = remainder_qty
                else:
                    break
            else:
                remaining_in_current_bale = bale_qty

    # Update totals
    job_card_doc.custom_total_segregated_qty = total_available
    job_card_doc.custom_total_bales_qty_planned = total_available

    job_card_doc.save()

    total_bales = full_bales_count + (1 if remainder_qty > 0 else 0)
    return {
        "success": True,
        "message": f"Generated plan for {total_bales} bales",
        "bales_count": total_bales
    }


def create_bales_from_plan(job_card_doc, stock_entry_doc):
    """
    Create Bales based on Job Card's Bales Plan.

    This function is called from create_bales_from_manufacture when
    the Job Card has custom_bales_plan entries.

    Args:
        job_card_doc: Job Card document
        stock_entry_doc: Stock Entry document (Manufacture)

    Returns:
        list: Names of created bales
    """
    if not hasattr(job_card_doc, 'custom_bales_plan') or not job_card_doc.custom_bales_plan:
        return []

    created_bales = []

    # Group plan entries by bale_number
    bales_by_number = {}
    for entry in job_card_doc.custom_bales_plan:
        bale_num = entry.bale_number
        if bale_num not in bales_by_number:
            bales_by_number[bale_num] = {
                "packed_item": entry.packed_item,
                "bale_qty": entry.bale_qty,
                "packaging_materials": []
            }
        bales_by_number[bale_num]["packaging_materials"].append({
            "item_code": entry.packaging_item,
            "qty": flt(entry.batch_qty_used),
            "batch_no": entry.batch_no,
            "sub_batch": entry.sub_batch or "",
            "warehouse": stock_entry_doc.to_warehouse or ""
        })

    # Get warehouse from finished item in Stock Entry
    target_warehouse = None
    for item in stock_entry_doc.items:
        if item.is_finished_item:
            target_warehouse = item.t_warehouse
            break

    # Extract FG item rows with batches from Stock Entry, grouped by bale number
    # Pass bales_by_number for qty-based distribution
    fg_items_by_bale = extract_fg_items_by_bale(stock_entry_doc, bales_by_number)

    # Create bales for each unique bale_number
    for bale_num, bale_data in sorted(bales_by_number.items()):
        bale_qty = flt(bale_data["bale_qty"])

        # Get custom_bale_qty from item to determine if partial
        standard_bale_qty = frappe.db.get_value(
            "Item", bale_data["packed_item"], "custom_bale_qty"
        ) or 0
        is_partial = bale_qty < flt(standard_bale_qty)

        # Get packed items (FG batches) for this bale
        packed_items = fg_items_by_bale.get(bale_num, [])

        bale_name = create_single_bale(
            item_code=bale_data["packed_item"],
            qty=bale_qty,
            warehouse=target_warehouse,
            packaging_materials=bale_data["packaging_materials"],
            stock_entry=stock_entry_doc.name,
            job_card=job_card_doc.name,
            work_order=job_card_doc.work_order,
            source="Manufacture",
            is_partial=is_partial,
            packed_items=packed_items
        )

        if bale_name:
            created_bales.append(bale_name)

    return created_bales


def extract_fg_items_by_bale(stock_entry_doc, bales_by_number=None):
    """
    Extract finished goods items with their batches from Stock Entry,
    grouped by bale number.

    FG items are distributed to bales based on qty matching with bale plan.
    Each FG item row in Stock Entry corresponds to one bale.

    Args:
        stock_entry_doc: Stock Entry document (Manufacture)
        bales_by_number: Dict of bale plan data {bale_num: {bale_qty, ...}}

    Returns:
        dict: {bale_number: [{"item_code", "item_name", "qty", "batch_no", "sub_batch", "warehouse"}]}
    """
    fg_items_by_bale = {}

    # Note: Stock Entry is now fetched fresh after database commit via enqueue
    # so Serial and Batch Bundles should already be available

    # Collect all FG items with their batches
    fg_items = []
    for item in stock_entry_doc.items:
        if not item.is_finished_item:
            continue

        # Get batch info from serial_and_batch_bundle or batch_no
        batch_no = None
        sub_batch = getattr(item, 'custom_sub_batch', '') or ""

        if item.serial_and_batch_bundle:
            # Get batch from Serial and Batch Bundle
            try:
                bundle = frappe.get_doc("Serial and Batch Bundle", item.serial_and_batch_bundle)
                if bundle.entries:
                    batch_no = bundle.entries[0].batch_no
            except Exception:
                pass

        if not batch_no:
            batch_no = item.batch_no

        if not batch_no:
            # Log warning but continue - FG item without batch
            frappe.log_error(
                f"FG item {item.item_code} in SE {stock_entry_doc.name} has no batch",
                "Bales - FG Item No Batch"
            )
            continue

        fg_items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": flt(item.qty),
            "batch_no": batch_no,
            "sub_batch": sub_batch,
            "warehouse": item.t_warehouse
        })

    if not fg_items:
        frappe.log_error(
            f"No FG items with batches found in SE {stock_entry_doc.name}",
            "Bales - No FG Items"
        )
        return fg_items_by_bale

    # If no bales_by_number provided, assign all FG items to bale 1
    if not bales_by_number:
        fg_items_by_bale[1] = fg_items
        return fg_items_by_bale

    # Distribute FG items to bales based on bale_qty
    # Each bale should get FG items whose total qty = bale's bale_qty
    sorted_bales = sorted(bales_by_number.items(), key=lambda x: x[0])

    # Sort FG items by qty for better allocation
    fg_items_remaining = fg_items.copy()

    for bale_num, bale_data in sorted_bales:
        target_qty = flt(bale_data.get("bale_qty", 0))
        if target_qty <= 0:
            continue

        fg_items_by_bale[bale_num] = []
        allocated_qty = 0

        # Find FG items to fill this bale's qty
        items_to_remove = []
        for i, fg in enumerate(fg_items_remaining):
            if allocated_qty >= target_qty:
                break

            fg_qty = flt(fg["qty"])
            remaining_needed = target_qty - allocated_qty

            if fg_qty <= remaining_needed:
                # Take entire FG item
                fg_items_by_bale[bale_num].append(fg.copy())
                allocated_qty += fg_qty
                items_to_remove.append(i)
            else:
                # Split FG item - take only what's needed
                partial_fg = fg.copy()
                partial_fg["qty"] = remaining_needed
                fg_items_by_bale[bale_num].append(partial_fg)
                allocated_qty += remaining_needed
                # Reduce remaining qty in original
                fg["qty"] = fg_qty - remaining_needed

        # Remove fully allocated items (in reverse order to maintain indices)
        for i in reversed(items_to_remove):
            fg_items_remaining.pop(i)

    # Log for debugging
    distribution_detail = []
    for bale_num, items in fg_items_by_bale.items():
        total_qty = sum(flt(item["qty"]) for item in items)
        distribution_detail.append(f"Bale {bale_num}: {total_qty} qty")

    frappe.log_error(
        f"SE: {stock_entry_doc.name}\n"
        f"FG Items: {len(fg_items)}\n"
        f"Bales: {list(bales_by_number.keys())}\n"
        f"Distribution: {distribution_detail}",
        "Bales - FG Distribution"
    )

    return fg_items_by_bale
