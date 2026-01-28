# Copyright (c) 2025, TCB Infotechpvtltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class DeliveryNoteBales(Document):
    def validate(self):
        self.calculate_totals()

    def calculate_totals(self):
        """Calculate total bales and qty"""
        self.total_bales = len(self.bales) if self.bales else 0
        self.total_qty = (
            sum(flt(row.qty) for row in self.bales) if self.bales else 0
        )

    def on_trash(self):
        """Allow deletion without blocking - just update status"""
        # Don't block deletion - allows DN cancel/delete to work smoothly
        pass


@frappe.whitelist()
def get_or_create_bales_doc(delivery_note):
    """Get existing or create new Delivery Note Bales document"""
    existing = frappe.db.get_value(
        "Delivery Note Bales", {"delivery_note": delivery_note}, "name"
    )

    if existing:
        return frappe.get_doc("Delivery Note Bales", existing)

    # Create new
    doc = frappe.new_doc("Delivery Note Bales")
    doc.delivery_note = delivery_note
    return doc


@frappe.whitelist()
def add_bales_to_delivery_note(
    delivery_note, bales_data, dn_item_row_name=None
):
    """Add bales to the Delivery Note Bales document"""
    import json

    if isinstance(bales_data, str):
        bales_data = json.loads(bales_data)

    frappe.log_error(
        "Adding Bales",
        f"Delivery Note: {delivery_note}\n"
        f"Bales Data: {bales_data}\n"
        f"DN Item Row: {dn_item_row_name}",
    )

    # Get or create the bales document
    doc = get_or_create_bales_doc(delivery_note)

    # Get existing bale names to avoid duplicates
    existing_bales = {row.bale for row in doc.bales} if doc.bales else set()

    # Add new bales
    for bale_info in bales_data:
        if bale_info["name"] not in existing_bales:
            doc.append(
                "bales",
                {
                    "bale": bale_info["name"],
                    "item": bale_info.get("item"),
                    "qty": bale_info.get("qty") or bale_info.get("bale_qty"),
                    "batch_count": bale_info.get("batch_count", 0),
                    "delivery_note": delivery_note,
                    "dn_item": dn_item_row_name,
                },
            )

    doc.save(ignore_permissions=True)
    return doc


@frappe.whitelist()
def get_bales_for_delivery_note(delivery_note):
    """Get all bales linked to a Delivery Note"""
    doc_name = frappe.db.get_value(
        "Delivery Note Bales", {"delivery_note": delivery_note}, "name"
    )

    if not doc_name:
        return {"bales": [], "total_bales": 0, "total_qty": 0}

    doc = frappe.get_doc("Delivery Note Bales", doc_name)

    bales = []
    for row in doc.bales:
        bale_data = {
            "bale": row.bale,
            "item": row.item,
            "qty": row.qty,
            "batch_count": row.batch_count,
        }

        # Get bale status
        bale_status = frappe.db.get_value("Bales", row.bale, "bales_status")
        bale_data["bales_status"] = bale_status

        bales.append(bale_data)

    return {
        "bales": bales,
        "total_bales": doc.total_bales,
        "total_qty": doc.total_qty,
    }


@frappe.whitelist()
def delete_bales_doc_for_delivery_note(delivery_note):
    """Delete Delivery Note Bales document when DN is cancelled/deleted"""
    doc_name = frappe.db.get_value(
        "Delivery Note Bales", {"delivery_note": delivery_note}, "name"
    )

    if doc_name:
        frappe.delete_doc("Delivery Note Bales", doc_name, force=True)
        return True

    return False


@frappe.whitelist()
def get_assigned_bales_qty_for_item(
    delivery_note, item_code, dn_item_row_name=None
):
    """
    Get total assigned bales qty for a specific item row in DN.
    Used to calculate remaining qty for bale assignment.

    Args:
        delivery_note: Delivery Note name
        item_code: Item code
        dn_item_row_name: DN Item row name (optional, row-wise calc)
    """
    doc_name = frappe.db.get_value(
        "Delivery Note Bales", {"delivery_note": delivery_note}, "name"
    )

    if not doc_name:
        return {"assigned_qty": 0, "bales_count": 0}

    # If dn_item_row_name provided, get row-specific assigned qty
    if dn_item_row_name:
        result = frappe.db.sql(
            """
            SELECT SUM(qty) as total_qty, COUNT(*) as bales_count
            FROM `tabDelivery Note Bales Detail`
            WHERE parent = %s AND item = %s AND dn_item = %s
            """,
            (doc_name, item_code, dn_item_row_name),
            as_dict=True,
        )
    else:
        # Fallback to item-level calculation (for backward compatibility)
        result = frappe.db.sql(
            """
            SELECT SUM(qty) as total_qty, COUNT(*) as bales_count
            FROM `tabDelivery Note Bales Detail`
            WHERE parent = %s AND item = %s
            """,
            (doc_name, item_code),
            as_dict=True,
        )

    if result and result[0]:
        return {
            "assigned_qty": flt(result[0].total_qty),
            "bales_count": result[0].bales_count or 0,
        }

    return {"assigned_qty": 0, "bales_count": 0}


@frappe.whitelist()
def remove_bale_from_delivery_note(delivery_note, bale_name, item_code):
    """
    Remove a specific bale from DN Bales and update Bundle.

    Args:
        delivery_note: Delivery Note name
        bale_name: Bale to remove
        item_code: Item code of the bale
    """
    # Check if DN is draft
    dn_status = frappe.db.get_value(
        "Delivery Note", delivery_note, "docstatus"
    )
    if dn_status != 0:
        frappe.throw(
            _("Cannot remove bales from submitted Delivery Note")
        )

    # Get Delivery Note Bales doc
    doc_name = frappe.db.get_value(
        "Delivery Note Bales", {"delivery_note": delivery_note}, "name"
    )

    if not doc_name:
        frappe.throw(_("No bales document found for this Delivery Note"))

    doc = frappe.get_doc("Delivery Note Bales", doc_name)

    # Find and remove the bale from child table
    bale_to_remove = None
    for row in doc.bales:
        if row.bale == bale_name and row.item == item_code:
            bale_to_remove = row
            doc.remove(row)
            break

    if not bale_to_remove:
        frappe.throw(
            _("Bale {0} not found in Delivery Note Bales").format(
                bale_name
            )
        )

    # Get dn_item (DN Item row name) to update the correct item row
    dn_item_row_name = bale_to_remove.dn_item

    # Save the Delivery Note Bales doc to recalculate totals
    doc.save(ignore_permissions=True)

    # Get the DN Item row to update
    dn_doc = frappe.get_doc("Delivery Note", delivery_note)
    dn_item_row = None

    for item in dn_doc.items:
        if item.name == dn_item_row_name:
            dn_item_row = item
            break

    if not dn_item_row:
        frappe.throw(_("Delivery Note Item row not found"))

    # Get the Serial and Batch Bundle
    bundle_name = dn_item_row.serial_and_batch_bundle

    if bundle_name:
        # Get batch entries from the bale
        bale_doc = frappe.get_doc("Bales", bale_name)
        bale_batch_entries = {
            entry.batch_no: flt(entry.qty)
            for entry in bale_doc.get("packed_items", [])
        }

        # Remove matching entries from Serial and Batch Bundle
        bundle_doc = frappe.get_doc("Serial and Batch Bundle", bundle_name)

        entries_to_remove = []
        for entry in bundle_doc.entries:
            if entry.batch_no in bale_batch_entries:
                # Remove this entry (negative qty in bundle)
                entries_to_remove.append(entry)

        for entry in entries_to_remove:
            bundle_doc.remove(entry)

        # Recalculate bundle total
        bundle_total = sum(
            abs(flt(entry.qty)) for entry in bundle_doc.entries
        )

        if bundle_total == 0:
            # If no entries left, remove the bundle reference
            dn_item_row.serial_and_batch_bundle = None
            frappe.delete_doc(
                "Serial and Batch Bundle", bundle_name, force=True
            )
            # Save DN to clear bundle reference
            dn_doc.save(ignore_permissions=True)
        else:
            # Save bundle with updated entries
            bundle_doc.save(ignore_permissions=True)

    # Update bale status back to Packed
    bale_doc = frappe.get_doc("Bales", bale_name)
    source_doc_type = bale_doc.source_document_type

    if source_doc_type == "Purchase Receipt":
        new_status = "Packed Import"
    else:
        new_status = "Packed In House"

    frappe.db.set_value(
        "Bales",
        bale_name,
        {"bales_status": new_status, "delivery_note": None},
        update_modified=True,
    )

    # Return updated totals
    return {
        "success": True,
        "total_bales": doc.total_bales,
        "total_qty": doc.total_qty,
    }
