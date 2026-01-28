# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class Bales(Document):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def before_insert(self):
        """Set initial status based on bales source"""
        self.set_initial_status()

    def validate(self):
        """Validate status transitions"""
        self.validate_status_transition()

    def before_cancel(self):
        """
        Block direct cancellation of Bales.
        Cancel authority depends on source_document_type:
        - Manufacture (Bales Creator): Controlled by Stock Entry
        - Import (Purchase Receipt): Controlled by Purchase Receipt

        Each controller sets its own flag before cancelling Bales.

        Also allows cancellation via Frappe's linked document cancellation flow
        (cancel_all_linked_docs) when the parent Stock Entry is being cancelled.
        """
        # IMPORT FLOW: Controlled by Purchase Receipt
        if self.source_document_type == "Purchase Receipt":
            # Allow if triggered from Purchase Receipt cancel flow
            if frappe.flags.get("purchase_receipt_bale_cancel"):
                return
            # Allow if triggered from Frappe's linked doc cancellation via Purchase Receipt
            if self._is_linked_doc_cancel_from_pr():
                return
            # Block direct cancellation
            frappe.throw(
                _(
                    "Import Bales are controlled by Purchase Receipt. "
                    "Please cancel the linked Purchase Receipt instead."
                )
            )
        
        elif self.source_document_type == "Bales Creator":
            self.flags.ignore_links = True
            return

        # RE-BALE FLOW: Controlled by Re-Bale document
        if frappe.flags.get("rebale_bale_cancel"):
            return

        # OPENING STOCK FLOW: Controlled by Bales Creator directly (no Stock Entry)
        if frappe.flags.get("opening_stock_bale_cancel"):
            return

        # MANUFACTURE FLOW: Controlled by Stock Entry
        # Allow ONLY if cancel is triggered from Stock Entry cancel flow
        if frappe.flags.get("stock_entry_bale_cancel"):
            return

        # Allow if triggered from Frappe's linked doc cancellation via Stock Entry
        if self._is_linked_doc_cancel_from_stock_entry():
            return

        # Block ALL other attempts - including direct user cancel and Bales Creator cancel
        frappe.throw(
            _(
                "Bales are controlled by Stock Entry. "
                "Please cancel the linked Stock Entry instead."
            )
        )

    def _is_linked_doc_cancel_from_stock_entry(self):
        """
        Check if this cancel is triggered from Frappe's cancel_all_linked_docs
        when a Stock Entry is being cancelled.

        This happens when:
        1. User cancels a Stock Entry
        2. Frappe detects linked Bales
        3. User confirms to cancel linked docs
        4. Frappe calls cancel_all_linked_docs which cancels Bales
        """
        # Check if we're in the linked doc cancel flow
        import inspect
        for frame_info in inspect.stack():
            if frame_info.function == "cancel_all_linked_docs":
                # Set flag to ignore link checks during this cancel
                self.flags.ignore_links = True
                return True

        # Check if there's a linked Stock Entry that references this Bale
        if self.material_consumption_entry:
            se_docstatus = frappe.db.get_value(
                "Stock Entry", self.material_consumption_entry, "docstatus"
            )
            # If Stock Entry is being cancelled (docstatus will change to 2 after)
            # Allow the linked doc cancel
            if se_docstatus == 1:
                self.flags.ignore_links = True
                return True
        return False

    def _is_linked_doc_cancel_from_pr(self):
        """
        Check if this cancel is triggered from Frappe's cancel_all_linked_docs
        when a Purchase Receipt is being cancelled.
        """
        import inspect
        for frame_info in inspect.stack():
            if frame_info.function == "cancel_all_linked_docs":
                # Set flag to ignore link checks during this cancel
                self.flags.ignore_links = True
                return True

        if self.source_document_type == "Purchase Receipt" and self.source_document:
            pr_docstatus = frappe.db.get_value(
                "Purchase Receipt", self.source_document, "docstatus"
            )
            if pr_docstatus == 1:
                self.flags.ignore_links = True
                return True
        return False

    def on_submit(self):
        """Create Bales Ledger Entry on submit"""
        self.create_bales_ledger_entries()

    def on_cancel(self):
        """Clean up on cancel"""
        self.delete_bales_ledger_entries()
        self.cancel_material_consumption_entry()
        if self.source_document_type == "Bales Creator":
            self.source_document_type = ""
            self.source_document = ""
            frappe.db.commit()

    def on_trash(self):
        """Clean up on delete"""
        if self.source_document_type == "Bales Creator":
            self.flags.ignore_links = True
        self.delete_bales_ledger_entries()

    def set_initial_status(self):
        """
        Set initial status based on source_document_type.

        Source is derived from source_document_type field:
        - 'Stock Entry' → Manufacture → status = 'Packed In House'
        - 'Purchase Receipt' → Import → status = 'Packed Import'
        - 'Re-Bale' → Re-Pack → status = 'Packed In House'
        - 'Bales Creator' → Old flow → status = 'Require Packing'

        Note: If status is already set (by create_single_bale), don't override it.
        """
        # If status is already explicitly set, don't override
        if self.bales_status and self.bales_status != "Require Packing":
            return

        if self.source_document_type == "Purchase Receipt":
            # Import bales go directly to Packed Import
            self.bales_status = "Packed Import"
        elif self.source_document_type == "Re-Bale":
            # Re-Bale bales go to Packed In House
            self.bales_status = "Packed In House"
        elif self.source_document_type == "Stock Entry":
            # Manufacture bales from new Manufacturing flow go to Packed In House
            self.bales_status = "Packed In House"
        else:
            # Old Bales Creator flow - start at Require Packing
            self.bales_status = "Require Packing"

    def validate_status_transition(self):
        """Validate that status transitions follow the allowed path"""
        if self.is_new():
            return

        old_status = frappe.db.get_value("Bales", self.name, "bales_status")

        if old_status == self.bales_status:
            return

        allowed_transitions = {
            "Require Packing": ["Packed In House"],
            "Packed In House": ["Need Approval", "Require Packing", "Re-Packed", "Dispatched"],
            "Need Approval": ["Packed Import", "Packed In House"],
            "Packed Import": ["Dispatched", "Re-Packed"],
            "Dispatched": ["Packed Import", "Packed In House"],  # Allow reverting on DN cancel
            "Re-Packed": [],  # Final status - no further transitions
        }

        if old_status and self.bales_status not in allowed_transitions.get(
            old_status, []
        ):
            frappe.throw(
                _("Status cannot be changed from {0} to {1}").format(
                    old_status, self.bales_status
                )
            )

    def create_bales_ledger_entries(self):
        """Create Bales Ledger Entry for each batch used"""
        for batch_row in self.batches_used:
            if not frappe.db.exists(
                "Bales Ledger Entry", {"bales": self.name, "batch": batch_row.batch}
            ):
                ledger_entry = frappe.new_doc("Bales Ledger Entry")
                ledger_entry.bales = self.name
                ledger_entry.item_code = self.item
                ledger_entry.warehouse = self.warehouse
                ledger_entry.batch = batch_row.batch
                ledger_entry.sub_batch = batch_row.sub_batch
                ledger_entry.qty_consumed = batch_row.qty_taken
                ledger_entry.posting_date = self.posting_date or today()
                ledger_entry.insert(ignore_permissions=True)

    def delete_bales_ledger_entries(self):
        """Delete related Bales Ledger Entries"""
        frappe.db.delete("Bales Ledger Entry", {"bales": self.name})

    def cancel_material_consumption_entry(self):
        """
        Cancel the linked Material Consumption Stock Entry if exists.

        NOTE: This is skipped when Bales cancel is triggered FROM the Stock Entry cancel flow,
        as the Stock Entry is already being cancelled.
        """
        # Skip if we're being cancelled from Stock Entry flow
        # (The Stock Entry is already handling its own cancellation)
        if frappe.flags.get("stock_entry_bale_cancel"):
            return

        # Skip if we're in the cancel_all_linked_docs flow
        import inspect
        for frame_info in inspect.stack():
            if frame_info.function == "cancel_all_linked_docs":
                return

        if self.material_consumption_entry:
            try:
                stock_entry = frappe.get_doc(
                    "Stock Entry", self.material_consumption_entry
                )
                if stock_entry.docstatus == 1:
                    # Set flag to allow the Stock Entry cancel to cascade to other Bales
                    frappe.flags.stock_entry_bale_cancel = True
                    try:
                        stock_entry.flags.ignore_links = True
                        stock_entry.cancel()
                    finally:
                        frappe.flags.stock_entry_bale_cancel = False
            except Exception as e:
                # Use shorter title for error log (max 140 chars)
                frappe.log_error(
                    message=str(e),
                    title="Bales SE Cancel Error"
                )


@frappe.whitelist()
def update_bales_status(bales_name, new_status):
    """
    Update bales status via API call.
    Used for status transitions from frontend.
    """
    if not bales_name or not new_status:
        frappe.throw(_("Bales name and new status are required"))

    bales_doc = frappe.get_doc("Bales", bales_name)

    # Check if status transition is valid
    old_status = bales_doc.bales_status

    allowed_transitions = {
        "Require Packing": ["Packed In House"],
        "Packed In House": ["Need Approval", "Require Packing", "Re-Packed"],
        "Need Approval": ["Packed Import", "Packed In House"],
        "Packed Import": ["Dispatched", "Re-Packed"],
        "Dispatched": ["Packed Import"],
        "Re-Packed": [],  # Final status - no further transitions
    }

    if new_status not in allowed_transitions.get(old_status, []):
        frappe.throw(
            _("Status cannot be changed from {0} to {1}").format(old_status, new_status)
        )

    bales_doc.bales_status = new_status
    bales_doc.save(ignore_permissions=True)

    return {"success": True, "message": f"Status updated to {new_status}"}


@frappe.whitelist()
def get_bales_for_delivery_note(delivery_note_name):
    """
    Get available bales based on batches in Delivery Note items.
    Returns bales with status = 'Packed Import' or 'Packed In House'.
    """
    doc = frappe.get_doc("Delivery Note", delivery_note_name)
    all_bales = set()

    if not doc.items:
        return []

    # Get all batches from Serial and Batch Bundle
    bundles = {}
    for item in doc.items:
        if item.serial_and_batch_bundle:
            sabb = frappe.get_doc(
                "Serial and Batch Bundle", item.serial_and_batch_bundle
            )
            batches = [e.batch_no for e in sabb.entries]
            if item.item_code not in bundles:
                bundles[item.item_code] = []
            bundles[item.item_code].extend(batches)

    # Find bales containing these batches
    # Eligible statuses for dispatch
    eligible_statuses = ["Packed Import", "Packed In House"]

    for item_code, batch_list in bundles.items():
        for batch_no in batch_list:
            bale_batches = frappe.get_all(
                "Bales Batches", filters={"batch": batch_no}, fields=["parent"]
            )

            for bale_batch in bale_batches:
                bales_doc = frappe.get_doc("Bales", bale_batch.parent)
                # Include bales with eligible status and docstatus = 1
                if bales_doc.bales_status in eligible_statuses and bales_doc.docstatus == 1:
                    all_bales.add(bale_batch.parent)

    # Get already added bales from Delivery Note Bales doctype
    doc_name = frappe.db.get_value(
        "Delivery Note Bales", {"delivery_note": delivery_note_name}, "name"
    )
    present_bales = []
    if doc_name:
        present_bales = frappe.get_all(
            "Delivery Note Bales Detail",
            filters={"parent": doc_name},
            pluck="bale"
        )

    # Return only new bales
    new_bales = [b for b in all_bales if b not in present_bales]

    return new_bales


@frappe.whitelist()
def dispatch_bales(bales_list, delivery_note_name):
    """
    Update bales status to 'Dispatched' and link to Delivery Note.
    Called when Delivery Note is submitted.
    """
    if isinstance(bales_list, str):
        import json

        bales_list = json.loads(bales_list)

    # Eligible statuses for dispatch
    eligible_statuses = ["Packed Import", "Packed In House"]

    for bales_name in bales_list:
        try:
            bales_doc = frappe.get_doc("Bales", bales_name)
            if bales_doc.bales_status in eligible_statuses:
                bales_doc.bales_status = "Dispatched"
                bales_doc.delivery_note = delivery_note_name
                bales_doc.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Error dispatching bale {bales_name}: {str(e)}")


@frappe.whitelist()
def revert_bales_dispatch(bales_list):
    """
    Revert bales status from 'Dispatched' to original status based on source.
    Called when Delivery Note is cancelled.

    - Stock Entry (Manufacture) → Packed In House
    - Purchase Receipt (Import) → Packed Import
    """
    if isinstance(bales_list, str):
        import json

        bales_list = json.loads(bales_list)

    for bales_name in bales_list:
        try:
            bales_doc = frappe.get_doc("Bales", bales_name)
            if bales_doc.bales_status == "Dispatched":
                # Revert to appropriate status based on source
                if bales_doc.source_document_type == "Purchase Receipt":
                    bales_doc.bales_status = "Packed Import"
                else:
                    # Manufacture (Stock Entry) or others
                    bales_doc.bales_status = "Packed In House"
                bales_doc.delivery_note = None
                bales_doc.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Error reverting bale {bales_name}: {str(e)}")


@frappe.whitelist()
def create_bales_from_purchase_receipt(purchase_receipt_name):
    """
    Create Bales from Purchase Receipt (Import flow).
    This is the Import flow that creates bales with status = 'Available'.
    """
    from frappe.utils import getdate

    doc = frappe.get_doc("Purchase Receipt", purchase_receipt_name)

    if doc.docstatus != 1:
        frappe.throw(_("Purchase Receipt must be submitted first"))

    if doc.custom_bales_created:
        frappe.throw(_("Bales have already been created for this Purchase Receipt"))

    created_bales = []

    for item in doc.items:
        if not item.item_code or not item.serial_and_batch_bundle:
            continue

        # Check if item is in segregated group
        item_group = frappe.db.get_value("Item", item.item_code, "item_group")
        if item_group != "ad*star bags segregated":
            continue

        # Get item bale qty for reference
        item_bale_qty = (
            frappe.db.get_value("Item", item.item_code, "custom_bale_qty") or 0
        )

        # Get batches from Serial and Batch Bundle
        sabb = frappe.get_doc("Serial and Batch Bundle", item.serial_and_batch_bundle)

        # Create a single bale for each item in the PR
        bales_doc = frappe.new_doc("Bales")
        bales_doc.item = item.item_code
        bales_doc.warehouse = item.warehouse
        bales_doc.posting_date = getdate()
        bales_doc.bales_source = "Import"  # Must match Bales Source doctype
        bales_doc.source_document_type = "Purchase Receipt"
        bales_doc.source_document = purchase_receipt_name

        total_qty = 0
        for entry in sabb.entries:
            sub_batch = frappe.db.get_value("Batch", entry.batch_no, "custom_sub_batch")
            bales_doc.append(
                "batches_used",
                {
                    "item": item.item_code,
                    "batch": entry.batch_no,
                    "sub_batch": sub_batch,
                    "qty_taken": abs(entry.qty),
                    "warehouse": item.warehouse,
                },
            )
            total_qty += abs(entry.qty)

        bales_doc.bale_qty = total_qty

        # Import bales go directly to Packed Import status
        bales_doc.bales_status = "Packed Import"

        # Save and submit
        bales_doc.insert()

        # Only submit if qty meets minimum requirement
        if item_bale_qty > 0 and total_qty >= item_bale_qty:
            bales_doc.submit()

        created_bales.append(bales_doc.name)

    # Mark PR as having bales created
    if created_bales:
        frappe.db.set_value(
            "Purchase Receipt", purchase_receipt_name, "custom_bales_created", 1
        )
        frappe.db.commit()

    return {
        "success": True,
        "message": f"Created {len(created_bales)} bales",
        "bales": created_bales,
    }
