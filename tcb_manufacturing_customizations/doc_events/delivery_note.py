import frappe
from frappe import _
from frappe.utils import flt


def get_bales_list_for_dn(delivery_note):
    """Get list of bale names from Delivery Note Bales doctype"""
    doc_name = frappe.db.get_value(
        "Delivery Note Bales", {"delivery_note": delivery_note}, "name"
    )
    if not doc_name:
        return []

    return frappe.get_all(
        "Delivery Note Bales Detail", filters={"parent": doc_name}, pluck="bale"
    )


@frappe.whitelist()
def fetch_bales(doc=None, method=None, docname=None):
    """
    Fetch bales based on batches used in delivery note items.
    Only fetch bales with bales_status in ('Packed Import', 'Packed In House') and docstatus = 1.

    Can be called:
    - As a hook with doc object
    - From client-side with docname parameter
    """
    # Handle client-side call with docname parameter
    if docname:
        doc = frappe.get_doc("Delivery Note", docname)
    # Handle both document object and document name
    elif isinstance(doc, str):
        doc = frappe.get_doc("Delivery Note", doc)
    elif doc is None:
        frappe.throw(_("Either doc or docname is required"))

    all_bales = set()

    if not doc.items:
        return list(all_bales)

    # Get all batches from Serial and Batch Bundle
    bundles = {}
    for item in doc.items:
        if item.serial_and_batch_bundle:
            try:
                sabb = frappe.get_doc(
                    "Serial and Batch Bundle", item.serial_and_batch_bundle
                )
                batches = [e.batch_no for e in sabb.entries if e.batch_no]
                if item.item_code not in bundles:
                    bundles[item.item_code] = []
                bundles[item.item_code].extend(batches)
            except Exception:
                pass

    # Find bales containing these batches
    for item_code, batch_list in bundles.items():
        for batch_no in batch_list:
            bale_batches = frappe.get_all(
                "Bales Batches", filters={"batch": batch_no}, fields=["parent"]
            )

            for bale_batch in bale_batches:
                # Check if bale is Available and submitted using bales_status field
                # Available statuses: "Packed Import" (from Purchase Receipt) or "Packed In House" (from Manufacture)
                bales_data = frappe.db.get_value(
                    "Bales",
                    bale_batch.parent,
                    ["bales_status", "docstatus"],
                    as_dict=True,
                )
                if (
                    bales_data
                    and bales_data.bales_status in ["Packed Import", "Packed In House"]
                    and bales_data.docstatus == 1
                ):
                    all_bales.add(bale_batch.parent)

    # Get already added bales from Delivery Note Bales doctype
    present_bales = get_bales_list_for_dn(doc.name)

    # Return only new bales that aren't already in the document
    new_bales = [b for b in all_bales if b not in present_bales]

    return new_bales


@frappe.whitelist()
def get_bales_for_dn_item(item_code, warehouse=None, exclude_bales=None):
    """
    Get available bales filtered by item_code (mandatory).
    Returns bales with status 'Packed Import' or 'Packed In House' that are submitted.

    Used for row-level bale selection in Delivery Note Item.

    Args:
        item_code: Item code to filter bales (required)
        warehouse: Warehouse filter (optional)
        exclude_bales: JSON list of bale names to exclude (optional)

    Returns:
        List of bales with their batch details
    """
    import json

    if not item_code:
        frappe.throw(_("Item Code is required"))

    filters = {
        "item": item_code,
        "bales_status": ["in", ["Packed Import", "Packed In House"]],
        "docstatus": 1,
    }

    if warehouse:
        filters["warehouse"] = warehouse

    bales = frappe.get_all(
        "Bales",
        filters=filters,
        fields=[
            "name",
            "item",
            "warehouse",
            "bale_qty",
            "bales_status",
            "source_document_type",
        ],
        order_by="creation asc",
    )

    # Debug: Log all bales for this item regardless of status
    all_bales_for_item = frappe.get_all(
        "Bales",
        filters={"item": item_code},
        fields=["name", "item", "bales_status", "docstatus"],
    )
    if not bales and all_bales_for_item:
        # Debug: Check exact string values for status
        status_details = []
        for b in all_bales_for_item:
            status_repr = repr(b.get("bales_status"))
            status_details.append(f"{b.get('name')}: status={status_repr}, docstatus={b.get('docstatus')}")

        frappe.log_error(
            f"Item: {item_code}\n"
            f"Filter used: {filters}\n"
            f"All bales for item with status details:\n" + "\n".join(status_details) + "\n"
            f"Eligible bales (Packed Import/In House, docstatus=1): {bales}",
            "Bales Debug - Found but not eligible"
        )

    # Exclude already used bales
    if exclude_bales:
        if isinstance(exclude_bales, str):
            exclude_bales = json.loads(exclude_bales)
        bales = [b for b in bales if b.name not in exclude_bales]

    # Add batch details for each bale
    result = []
    for bale in bales:
        bale_batches = frappe.get_all(
            "Bales Batches",
            filters={"parent": bale.name},
            fields=["batch", "sub_batch", "qty_taken", "item", "warehouse"],
        )
        bale["batches"] = bale_batches
        bale["batch_count"] = len(bale_batches)
        # Calculate total qty from batches (more accurate than bale_qty field)
        bale["total_batch_qty"] = sum(b.qty_taken or 0 for b in bale_batches)
        result.append(bale)

    return result


@frappe.whitelist()
def get_available_bales(
    item_code=None, warehouse=None, item_codes=None, exclude_bales=None
):
    """
    Get available bales for dispatch based on optional filters.
    Returns bales with status 'Packed Import' or 'Packed In House' that are submitted.

    Args:
        item_code: Single item code filter (optional)
        warehouse: Warehouse filter (optional)
        item_codes: JSON list of item codes to filter by (optional)
        exclude_bales: JSON list of bale names to exclude (optional)

    Each bale includes its batch details for multi-batch handling.
    """
    import json

    filters = {
        "bales_status": ["in", ["Packed Import", "Packed In House"]],
        "docstatus": 1,
    }

    # Handle item_codes list (from DN items)
    if item_codes:
        if isinstance(item_codes, str):
            item_codes = json.loads(item_codes)
        if item_codes:
            filters["item"] = ["in", item_codes]
    elif item_code:
        filters["item"] = item_code

    if warehouse:
        filters["warehouse"] = warehouse

    bales = frappe.get_all(
        "Bales",
        filters=filters,
        fields=[
            "name",
            "item",
            "warehouse",
            "bale_qty",
            "bales_status",
            "source_document_type",
        ],
        order_by="creation asc",
    )

    # Exclude already added bales
    if exclude_bales:
        if isinstance(exclude_bales, str):
            exclude_bales = json.loads(exclude_bales)
        bales = [b for b in bales if b.name not in exclude_bales]

    # Add batch details for each bale
    result = []
    for bale in bales:
        bale_batches = frappe.get_all(
            "Bales Batches",
            filters={"parent": bale.name},
            fields=["batch", "sub_batch", "qty_taken", "item", "warehouse"],
        )
        bale["batches"] = bale_batches
        bale["batch_count"] = len(bale_batches)
        result.append(bale)

    return result


@frappe.whitelist()
def validate_bales_for_dispatch(bale_names):
    """
    Validate that selected bales are still eligible for dispatch.
    Called before applying bales to Delivery Note.

    Args:
        bale_names: JSON list of bale names to validate

    Returns:
        dict with 'valid' boolean and 'errors' list if invalid
    """
    import json

    if isinstance(bale_names, str):
        bale_names = json.loads(bale_names)

    if not bale_names:
        return {"valid": False, "errors": [_("No bales selected")]}

    errors = []
    valid_bales = []

    for bale_name in bale_names:
        bale_data = frappe.db.get_value(
            "Bales",
            bale_name,
            ["name", "bales_status", "docstatus", "item", "bale_qty"],
            as_dict=True,
        )

        if not bale_data:
            errors.append(_("Bale {0} not found").format(bale_name))
            continue

        if bale_data.docstatus != 1:
            errors.append(_("Bale {0} is not submitted").format(bale_name))
            continue

        if bale_data.bales_status not in ["Packed Import", "Packed In House"]:
            errors.append(
                _("Bale {0} is not available for dispatch. Current status: {1}").format(
                    bale_name, bale_data.bales_status
                )
            )
            continue

        valid_bales.append(bale_name)

    if errors:
        return {"valid": False, "errors": errors, "valid_bales": valid_bales}

    return {"valid": True, "errors": [], "valid_bales": valid_bales}


@frappe.whitelist()
def get_bales_with_batches_bulk(bale_names):
    """
    Get multiple bales with their batch details in a single call.
    More efficient than calling get_bale_with_batches multiple times.

    Args:
        bale_names: JSON list of bale names

    Returns:
        List of bale data with batches
    """
    import json

    if isinstance(bale_names, str):
        bale_names = json.loads(bale_names)

    if not bale_names:
        return []

    result = []
    for bale_name in bale_names:
        try:
            bale_data = get_bale_with_batches(bale_name)
            if bale_data:
                result.append(bale_data)
        except Exception as e:
            frappe.log_error(message=str(e), title=f"Error fetching bale {bale_name}")

    return result


@frappe.whitelist()
def get_bale_with_batches(bale_name):
    """
    Get a single bale with its batch details.
    Used when adding a bale to Delivery Note to get batch info for DN items.

    Returns dict with bale info and list of batches.
    ERPNext constraint: Each DN item row can only have one batch.
    So multi-batch Bales will need multiple DN item rows.
    """
    if not bale_name:
        return None

    bale = frappe.get_doc("Bales", bale_name)

    if bale.docstatus != 1:
        frappe.throw(_("Bale {0} is not submitted").format(bale_name))

    if bale.bales_status not in ["Packed Import", "Packed In House"]:
        frappe.throw(
            _("Bale {0} is not available for dispatch. Current status: {1}").format(
                bale_name, bale.bales_status
            )
        )

    batches = []
    if bale.get("packed_items"):
        for batch_row in bale.packed_items:
            item_code = batch_row.item_code or bale.item
            # Fetch item_name and stock_uom for the item (mandatory fields for DN Item)
            item_details = frappe.db.get_value(
                "Item", item_code, ["item_name", "stock_uom"], as_dict=True
            )
            batches.append(
                {
                    "batch": batch_row.batch_no,
                    "sub_batch": batch_row.sub_batch,
                    "qty": batch_row.qty,
                    "item_code": item_code,
                    "item_name": item_details.item_name if item_details else item_code,
                    "uom": item_details.stock_uom if item_details else "Kg",
                    "warehouse": batch_row.warehouse or bale.warehouse,
                }
            )
    else:
        for batch_row in bale.batches_used:
            item_code = batch_row.item or bale.item
            # Fetch item_name and stock_uom for the item (mandatory fields for DN Item)
            item_details = frappe.db.get_value(
                "Item", item_code, ["item_name", "stock_uom"], as_dict=True
            )
            batches.append(
                {
                    "batch": batch_row.batch,
                    "sub_batch": batch_row.sub_batch,
                    "qty": batch_row.qty_taken,
                    "item_code": item_code,
                    "item_name": item_details.item_name if item_details else item_code,
                    "uom": item_details.stock_uom if item_details else "Kg",
                    "warehouse": batch_row.warehouse or bale.warehouse,
                }
            )

    return {
        "name": bale.name,
        "item": bale.item,
        "warehouse": bale.warehouse,
        "bale_qty": bale.bale_qty,
        "bales_status": bale.bales_status,
        "source_document_type": bale.source_document_type,
        "batches": batches,
    }


def update_bales_status_on_dispatch(doc, method=None):
    """
    Update bale status to 'Dispatched' when Delivery Note is submitted.

    Bales with status 'Packed Import' or 'Packed In House' can be dispatched.

    Status workflow:
    - Import (Purchase Receipt): Packed Import → Dispatched
    - Manufacture (Bales Creator): Packed In House → Dispatched (or via Packed Import)

    Uses db_set to bypass "update after submit" restriction on Bales doctype.
    """
    # Get bales from Delivery Note Bales doctype
    bales_list = get_bales_list_for_dn(doc.name)

    # Valid statuses for dispatch
    dispatchable_statuses = ("Packed Import", "Packed In House")

    if doc.docstatus == 1 and bales_list:
        for bale_name in bales_list:
            try:
                # Get current status
                current_status = frappe.db.get_value("Bales", bale_name, "bales_status")

                # Dispatch bales that are in dispatchable status
                if current_status in dispatchable_statuses:
                    # Use db_set to bypass "update after submit" restriction
                    frappe.db.set_value(
                        "Bales",
                        bale_name,
                        {
                            "bales_status": "Dispatched",
                            "delivery_note": doc.name,
                        },
                        update_modified=True,
                    )
                elif current_status != "Dispatched":
                    # Log warning if bale is not in correct status
                    frappe.log_error(
                        f"Bale {bale_name} has status '{current_status}', "
                        f"expected one of {dispatchable_statuses} for dispatch",
                        "Bales Dispatch Warning",
                    )
            except Exception as e:
                frappe.log_error(
                    f"Error updating bale {bale_name}: {str(e)[:100]}",
                    "Bales Dispatch Error",
                )


def revert_bales_status_on_cancel(doc, method=None):
    """
    Revert bale status and unlink all related documents when Delivery Note is cancelled.

    This function:
    1. Reverts Bales status from Dispatched to original status (Packed Import/Packed In House)
    2. Clears delivery_note link from Bales
    3. Deletes the Delivery Note Bales document

    Status workflow:
    - Import (Purchase Receipt): Packed Import → Dispatched → Packed Import
    - Manufacture (Bales Creator): Packed In House → Dispatched → Packed In House

    Note: Bales, Bales Creator, and Stock Entry are added to ignore_links_on_delete
    in hooks.py to prevent "Cancel All Documents" popup.
    """
    # Get bales from Delivery Note Bales doctype
    bales_list = get_bales_list_for_dn(doc.name)

    for bale_name in bales_list:
        try:
            # Get current status and source document type
            bale_data = frappe.db.get_value(
                "Bales",
                bale_name,
                ["bales_status", "source_document_type"],
                as_dict=True,
            )

            if not bale_data:
                continue

            # Only revert if currently Dispatched
            if bale_data.bales_status == "Dispatched":
                # Determine revert status based on source document type
                if bale_data.source_document_type == "Purchase Receipt":
                    revert_status = "Packed Import"
                else:
                    # Bales Creator or other source types revert to Packed In House
                    revert_status = "Packed In House"

                # Use db_set to bypass "update after submit" restriction
                # Clear delivery_note link to unlink from DN
                frappe.db.set_value(
                    "Bales",
                    bale_name,
                    {
                        "bales_status": revert_status,
                        "delivery_note": None,
                    },
                    update_modified=True,
                )
        except Exception as e:
            frappe.log_error(
                f"Error reverting bale {bale_name}: {str(e)[:100]}",
                "Bales Revert Error",
            )

    # Also delete the Delivery Note Bales document
    from tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales import (
        delete_bales_doc_for_delivery_note,
    )

    delete_bales_doc_for_delivery_note(doc.name)


@frappe.whitelist()
def refresh_bales_on_batch_change(docname):
    return
    """
    Refresh bales when batches are changed in delivery note items.
    Called from client-side when batch changes.
    """
    from tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales import (
        add_bales_to_delivery_note,
        delete_bales_doc_for_delivery_note,
    )

    doc = frappe.get_doc("Delivery Note", docname)

    # Delete existing Delivery Note Bales document
    delete_bales_doc_for_delivery_note(docname)

    # Fetch fresh bales
    new_bales = fetch_bales(doc)

    if new_bales:
        # Get bale details for adding to new doctype
        bales_data = []
        for bale_name in new_bales:
            bale_doc = frappe.get_doc("Bales", bale_name)
            # Calculate total qty from batches_used
            bale_total_qty = (
                sum(flt(b.qty_taken) for b in bale_doc.batches_used)
                if bale_doc.batches_used
                else flt(bale_doc.bale_qty)
            )
            batch_count = len(bale_doc.batches_used) if bale_doc.batches_used else 0

            bales_data.append(
                {
                    "name": bale_doc.name,
                    "item": bale_doc.item,
                    "qty": bale_total_qty,
                    "batch_count": batch_count,
                }
            )

        # Add bales to new doctype
        # if bales_data:
        #     add_bales_to_delivery_note(docname, bales_data)

    return {"bales_added": len(new_bales), "bales": new_bales}


def delete_linked_bales_doc(doc, method=None):
    """
    Delete linked Delivery Note Bales document when Delivery Note is deleted.

    This is called on_trash to clean up the link before deletion.
    The Delivery Note Bales document is linked via delivery_note field,
    which causes a LinkExistsError if not deleted first.
    """
    from tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales import (
        delete_bales_doc_for_delivery_note,
    )

    delete_bales_doc_for_delivery_note(doc.name)


@frappe.whitelist()
def create_serial_batch_bundle_from_bales(
    dn_name, dn_item_row_name, item_code, warehouse, company, bale_names
):
    """
    Link selected bales to a Delivery Note item row and create Serial Batch Bundle
    from the packed_items (FG batches) in the bales.

    This function:
    1. Collects packed_items (FG batches) from selected bales
    2. Creates/updates Serial and Batch Bundle for stock deduction
    3. Updates DN item qty
    4. Links bales via Delivery Note Bales doctype

    Args:
        dn_name: Delivery Note name
        dn_item_row_name: Delivery Note Item row name
        item_code: Item code for the DN item
        warehouse: Warehouse for the DN item
        company: Company
        bale_names: JSON list of bale names to include

    Returns:
        dict with bundle_name, total_qty and bales_added list
    """
    import json
    from frappe.utils import now_datetime

    if isinstance(bale_names, str):
        bale_names = json.loads(bale_names)

    if not bale_names:
        frappe.throw(_("No bales selected"))

    # Validate all bales first
    validation = validate_bales_for_dispatch(json.dumps(bale_names))
    if not validation.get("valid"):
        errors = validation.get("errors", [])
        frappe.throw(_("Bale validation failed: {0}").format(", ".join(errors)))

    # Collect bale information and packed items (FG batches)
    bales_added = []
    total_bales_qty = 0
    batch_qty_map = {}  # {batch_no: {"qty": qty, "warehouse": warehouse}}

    for bale_name in bale_names:
        bale = frappe.get_doc("Bales", bale_name)

        # Use bale_qty as the primary qty (this is the packaged item qty)
        bale_qty = flt(bale.bale_qty)

        # If bale_qty is 0, calculate from packed_items or batches_used (for backward compatibility)
        if not bale_qty:
            if bale.packed_items:
                bale_qty = sum(flt(pi.qty) for pi in bale.packed_items)
            elif bale.batches_used:
                bale_qty = sum(flt(b.qty_taken) for b in bale.batches_used)

        total_bales_qty += bale_qty

        # Collect packed_items (FG batches) for Serial and Batch Bundle
        if hasattr(bale, 'packed_items') and bale.packed_items:
            for pi in bale.packed_items:
                if pi.batch_no and pi.item_code == item_code:
                    batch_no = pi.batch_no
                    batch_warehouse = pi.warehouse or bale.warehouse or warehouse

                    if batch_no in batch_qty_map:
                        batch_qty_map[batch_no]["qty"] += flt(pi.qty)
                    else:
                        batch_qty_map[batch_no] = {
                            "qty": flt(pi.qty),
                            "warehouse": batch_warehouse
                        }

        batch_count = len(bale.packed_items) if hasattr(bale, 'packed_items') and bale.packed_items else 0

        bales_added.append({
            "name": bale.name,
            "item": bale.item,
            "qty": bale_qty,
            "bale_qty": bale.bale_qty,
            "batch_count": batch_count,
        })

    if total_bales_qty <= 0:
        frappe.throw(_("Selected bales have no quantity"))

    # Get DN document
    dn_doc = frappe.get_doc("Delivery Note", dn_name)
    now = now_datetime()
    bundle_name = None

    # Create Serial and Batch Bundle if we have packed_items (FG batches)
    if batch_qty_map:
        # Check for existing bundle on this row
        existing_bundle_name = None
        for item_row in dn_doc.items:
            if item_row.name == dn_item_row_name:
                existing_bundle_name = item_row.serial_and_batch_bundle
                break

        if existing_bundle_name and frappe.db.exists("Serial and Batch Bundle", existing_bundle_name):
            # Update existing bundle
            bundle = frappe.get_doc("Serial and Batch Bundle", existing_bundle_name)

            # Build map of existing batches
            existing_batch_map = {}
            for entry in bundle.entries:
                existing_batch_map[entry.batch_no] = entry

            # Add new batches or update qty
            for batch_no, batch_data in batch_qty_map.items():
                if batch_no in existing_batch_map:
                    # Update existing entry qty (negative for Outward)
                    existing_batch_map[batch_no].qty -= batch_data["qty"]
                else:
                    bundle.append("entries", {
                        "batch_no": batch_no,
                        "qty": batch_data["qty"] * -1,
                        "warehouse": batch_data["warehouse"],
                    })

            bundle.save(ignore_permissions=True)
            bundle_name = bundle.name
        else:
            # Create new bundle
            bundle = frappe.new_doc("Serial and Batch Bundle")
            bundle.company = company
            bundle.item_code = item_code
            bundle.warehouse = warehouse
            bundle.type_of_transaction = "Outward"
            bundle.voucher_type = "Delivery Note"
            bundle.voucher_no = dn_name
            bundle.voucher_detail_no = dn_item_row_name
            bundle.posting_date = now.date()
            bundle.posting_time = now.strftime("%H:%M:%S")

            for batch_no, batch_data in batch_qty_map.items():
                bundle.append("entries", {
                    "batch_no": batch_no,
                    "qty": batch_data["qty"] * -1,  # Negative for Outward
                    "warehouse": batch_data["warehouse"],
                })

            bundle.insert(ignore_permissions=True)
            bundle_name = bundle.name

        # Calculate total qty from bundle
        bundle_total_qty = sum(abs(flt(entry.qty)) for entry in bundle.entries)
    else:
        # No packed_items - use bale_qty for total
        bundle_total_qty = total_bales_qty

    # Update DN item row
    for item_row in dn_doc.items:
        if item_row.name == dn_item_row_name:
            if bundle_name:
                item_row.serial_and_batch_bundle = bundle_name
            item_row.qty = bundle_total_qty if batch_qty_map else total_bales_qty
            item_row.batch_no = None
            item_row.serial_no = None
            break

    dn_doc.save(ignore_permissions=True)

    # Add bales to Delivery Note Bales doctype
    from tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales import (
        add_bales_to_delivery_note,
    )

    add_bales_to_delivery_note(dn_name, bales_added, dn_item_row_name)
    frappe.db.commit()

    return {
        "bundle_name": bundle_name,
        "total_qty": bundle_total_qty if batch_qty_map else total_bales_qty,
        "bales_added": bales_added,
        "entries_count": len(batch_qty_map) if batch_qty_map else len(bales_added),
    }


def get_existing_bales_qty_for_dn_item(dn_name, item_code):
    """
    Get total qty from bales already assigned to a DN for a specific item.
    """
    from tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.delivery_note_bales.delivery_note_bales import (
        get_bales_for_delivery_note,
    )

    result = get_bales_for_delivery_note(dn_name)
    if not result or not result.get("bales"):
        return 0

    total_qty = 0
    for bale_info in result["bales"]:
        # Only count bales for this item
        if bale_info.get("item") == item_code:
            total_qty += flt(bale_info.get("qty", 0))

    return total_qty
