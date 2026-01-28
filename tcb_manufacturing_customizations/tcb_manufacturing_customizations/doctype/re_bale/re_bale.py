# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today


class ReBale(Document):
    def validate(self):
        self.validate_original_bale()
        self.validate_batches()
        self.calculate_new_qty()

    def before_submit(self):
        """Validate before submission"""
        self.validate_original_bale_status()
        self.validate_raw_material_warehouse()
        self.validate_raw_material_stock()

    def on_submit(self):
        """Create new Bale and Stock Entry on submit"""
        self.create_rebale_and_stock_entry()

    def on_cancel(self):
        """Clean up on cancel"""
        self.revert_rebale()

    def validate_original_bale(self):
        """Validate original bale exists and is valid"""
        if not self.original_bale:
            frappe.throw(_("Original Bale is required"))

        bale_data = frappe.db.get_value(
            "Bales",
            self.original_bale,
            ["docstatus", "bales_status", "item", "warehouse", "bale_qty"],
            as_dict=True,
        )

        if not bale_data:
            frappe.throw(_("Original Bale {0} not found").format(self.original_bale))

        if bale_data.docstatus != 1:
            frappe.throw(_("Original Bale {0} is not submitted").format(self.original_bale))

        valid_statuses = ["Packed Import", "Packed In House"]
        if bale_data.bales_status not in valid_statuses:
            frappe.throw(
                _("Original Bale {0} has status '{1}'. Only bales with status {2} can be re-baled").format(
                    self.original_bale, bale_data.bales_status, ", ".join(valid_statuses)
                )
            )

    def validate_original_bale_status(self):
        """Re-validate status just before submit in case it changed"""
        bale_status = frappe.db.get_value("Bales", self.original_bale, "bales_status")
        valid_statuses = ["Packed Import", "Packed In House"]

        if bale_status not in valid_statuses:
            frappe.throw(
                _("Original Bale {0} status has changed to '{1}'. Cannot proceed with re-bale").format(
                    self.original_bale, bale_status
                )
            )

    def validate_batches(self):
        """Validate batches table"""
        if not self.batches:
            frappe.throw(_("At least one batch row is required"))

        for idx, batch_row in enumerate(self.batches, start=1):
            if not batch_row.batch:
                frappe.throw(_("Row {0}: Batch is required").format(idx))

            if flt(batch_row.new_qty) <= 0:
                frappe.throw(_("Row {0}: New Qty must be greater than zero").format(idx))

            if flt(batch_row.new_qty) > flt(batch_row.original_qty):
                frappe.throw(
                    _("Row {0}: New Qty ({1}) cannot exceed Original Qty ({2})").format(
                        idx, batch_row.new_qty, batch_row.original_qty
                    )
                )

    def calculate_new_qty(self):
        """Calculate total new qty from batches"""
        total = sum(flt(row.new_qty) for row in self.batches) if self.batches else 0
        self.new_qty = total

    def validate_raw_material_warehouse(self):
        """Ensure raw_material_warehouse is selected"""
        if not self.raw_material_warehouse:
            frappe.throw(_("Raw Material Warehouse is required before submission"))

    def validate_raw_material_stock(self):
        """Validate sufficient raw material stock for packaging"""
        from tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.bales_creator.bales_creator import (
            get_bom_raw_materials_for_bale_item,
        )

        raw_materials = get_bom_raw_materials_for_bale_item(self.item_code, flt(self.new_qty))

        if not raw_materials:
            return

        insufficient_stock = []

        for rm in raw_materials:
            available_qty = flt(
                frappe.db.get_value(
                    "Bin",
                    {"item_code": rm["item_code"], "warehouse": self.raw_material_warehouse},
                    "actual_qty",
                )
            )

            if available_qty < flt(rm["required_qty"]):
                insufficient_stock.append(
                    {
                        "item_code": rm["item_code"],
                        "item_name": rm.get("item_name", rm["item_code"]),
                        "required_qty": rm["required_qty"],
                        "available_qty": available_qty,
                        "shortage": rm["required_qty"] - available_qty,
                    }
                )

        if insufficient_stock:
            error_items = []
            for item in insufficient_stock:
                error_items.append(
                    f"• {item['item_name']} ({item['item_code']}): "
                    f"Required: {item['required_qty']}, Available: {item['available_qty']}, "
                    f"Shortage: {item['shortage']}"
                )

            frappe.throw(
                _("Insufficient raw material stock in {0}:\n{1}").format(
                    self.raw_material_warehouse, "\n".join(error_items)
                )
            )

    def create_rebale_and_stock_entry(self):
        """Create new Bale and Stock Entry for re-baling"""
        # 1. Create new Bale (Draft)
        new_bale = self._create_new_bale()

        # 2. Create Stock Entry for packaging materials
        stock_entry_name = self._create_stock_entry(new_bale.name)

        # 3. Update original bale status to Re-Packed
        self._update_original_bale(new_bale.name)

        # 4. Update this document with references
        self.db_set("new_bale", new_bale.name)
        self.db_set("stock_entry", stock_entry_name)

        frappe.msgprint(
            _("Created new Bale {0} and Stock Entry {1}. Please submit the Stock Entry to complete the process.").format(
                new_bale.name, stock_entry_name
            ),
            indicator="green",
            alert=True,
        )

    def _create_new_bale(self):
        """Create new Bale document from re-bale"""
        # Get or create Re-Pack bales source
        rebale_source = get_rebale_bales_source()

        new_bale = frappe.new_doc("Bales")
        new_bale.item = self.item_code
        new_bale.warehouse = self.warehouse
        new_bale.bale_qty = self.new_qty
        new_bale.posting_date = self.posting_date or today()
        new_bale.bales_source = rebale_source

        # Source document tracking
        new_bale.source_document_type = "Re-Bale"
        new_bale.source_document = self.name

        # Re-bale tracking
        new_bale.is_rebale = 1
        new_bale.rebale_source = self.original_bale
        new_bale.rebale_document = self.name

        # Copy batches from Re-Bale Item to Bales Batches
        for batch_row in self.batches:
            new_bale.append(
                "batches_used",
                {
                    "item": self.item_code,
                    "batch": batch_row.batch,
                    "sub_batch": batch_row.sub_batch,
                    "qty_taken": batch_row.new_qty,
                    "warehouse": self.warehouse,
                },
            )

        new_bale.insert(ignore_permissions=True)
        return new_bale

    def _create_stock_entry(self, new_bale_name):
        """Create Stock Entry for packaging material consumption"""
        from tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.bales_creator.bales_creator import (
            get_bom_raw_materials_for_bale_item,
        )

        raw_materials = get_bom_raw_materials_for_bale_item(self.item_code, flt(self.new_qty))

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Issue"
        stock_entry.posting_date = self.posting_date or today()
        stock_entry.company = frappe.defaults.get_user_default("Company")

        # Reference fields
        stock_entry.custom_bales_creator = None  # Not from Bales Creator
        stock_entry.custom_bale_reference = f"Re-Bale: {self.name} → {new_bale_name}"

        # Add raw materials
        for material in raw_materials:
            stock_entry.append(
                "items",
                {
                    "item_code": material["item_code"],
                    "qty": material["required_qty"],
                    "s_warehouse": self.raw_material_warehouse,
                    "uom": material.get("uom"),
                },
            )

        stock_entry.insert(ignore_permissions=True)

        # Link Stock Entry to new Bale
        frappe.db.set_value("Bales", new_bale_name, "material_consumption_entry", stock_entry.name)

        return stock_entry.name

    def _update_original_bale(self, new_bale_name):
        """Update original bale status and references"""
        frappe.db.set_value(
            "Bales",
            self.original_bale,
            {
                "bales_status": "Re-Packed",
                "rebaled_to": new_bale_name,
                "rebale_document": self.name,
            },
            update_modified=True,
        )

    def revert_rebale(self):
        """Revert all changes when Re-Bale is cancelled"""
        # 1. Get original bale's previous status
        original_bale_data = frappe.db.get_value(
            "Bales",
            self.original_bale,
            ["source_document_type"],
            as_dict=True,
        )

        # Determine revert status based on original source
        if original_bale_data and original_bale_data.source_document_type == "Purchase Receipt":
            revert_status = "Packed Import"
        else:
            revert_status = "Packed In House"

        # 2. Revert original bale status
        frappe.db.set_value(
            "Bales",
            self.original_bale,
            {
                "bales_status": revert_status,
                "rebaled_to": None,
                "rebale_document": None,
            },
            update_modified=True,
        )

        # 3. Cancel/Delete Stock Entry if exists
        if self.stock_entry:
            try:
                se_doc = frappe.get_doc("Stock Entry", self.stock_entry)
                if se_doc.docstatus == 1:
                    se_doc.cancel()
                elif se_doc.docstatus == 0:
                    frappe.delete_doc("Stock Entry", self.stock_entry, force=True)
            except Exception as e:
                frappe.log_error(
                    message=str(e),
                    title=f"Re-Bale Cancel: SE Error {self.stock_entry}",
                )

        # 4. Cancel/Delete new Bale if exists
        if self.new_bale:
            try:
                new_bale_doc = frappe.get_doc("Bales", self.new_bale)
                if new_bale_doc.docstatus == 1:
                    # Set flag to allow cancellation
                    frappe.flags.rebale_bale_cancel = True
                    try:
                        new_bale_doc.flags.ignore_links = True
                        new_bale_doc.cancel()
                    finally:
                        frappe.flags.rebale_bale_cancel = False
                elif new_bale_doc.docstatus == 0:
                    frappe.delete_doc("Bales", self.new_bale, force=True)
            except Exception as e:
                frappe.log_error(
                    message=str(e),
                    title=f"Re-Bale Cancel: Bale Error {self.new_bale}",
                )

        frappe.msgprint(
            _("Re-Bale cancelled. Original bale {0} status reverted to {1}").format(
                self.original_bale, revert_status
            ),
            indicator="orange",
            alert=True,
        )


def get_rebale_bales_source():
    """Get or create 'Re-Pack' Bales Source record"""
    # Bales Source uses 'bales_source' field for name and value
    source_name = frappe.db.get_value("Bales Source", {"bales_source": "Re-Pack"}, "name")

    if not source_name:
        # Check if it exists by name directly (name = bales_source value)
        if frappe.db.exists("Bales Source", "Re-Pack"):
            source_name = "Re-Pack"
        else:
            # Create Re-Pack source if it doesn't exist
            source_doc = frappe.new_doc("Bales Source")
            source_doc.bales_source = "Re-Pack"
            source_doc.insert(ignore_permissions=True)
            source_name = source_doc.name

    return source_name


@frappe.whitelist()
def get_bale_details(bale_name):
    """
    Fetch bale details and batches for Re-Bale form.
    Called when user selects original_bale.
    """
    if not bale_name:
        return None

    bale = frappe.get_doc("Bales", bale_name)

    # Validate status
    valid_statuses = ["Packed Import", "Packed In House"]
    if bale.bales_status not in valid_statuses:
        frappe.throw(
            _("Bale {0} has status '{1}'. Only bales with status {2} can be re-baled").format(
                bale_name, bale.bales_status, ", ".join(valid_statuses)
            )
        )

    if bale.docstatus != 1:
        frappe.throw(_("Bale {0} is not submitted").format(bale_name))

    # Get batches
    batches = []
    for batch_row in bale.batches_used:
        batches.append(
            {
                "batch": batch_row.batch,
                "sub_batch": batch_row.sub_batch,
                "original_qty": batch_row.qty_taken,
                "new_qty": batch_row.qty_taken,  # Default new_qty = original_qty
                "item": batch_row.item or bale.item,
                "warehouse": batch_row.warehouse or bale.warehouse,
            }
        )

    return {
        "item_code": bale.item,
        "item_name": frappe.db.get_value("Item", bale.item, "item_name"),
        "warehouse": bale.warehouse,
        "original_qty": bale.bale_qty,
        "batches": batches,
    }
