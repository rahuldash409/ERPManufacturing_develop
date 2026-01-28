# Copyright (c) 2025, TCB Infotechpvtltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt


class ReleaseOrder(Document):
    def validate(self):
        self.validate_sales_order()
        self.validate_release_quantities()
        self.calculate_totals()

    def validate_sales_order(self):
        """Validate that Sales Order is submitted and not closed/cancelled"""
        if not self.sales_order:
            frappe.throw(_("Sales Order is required"))

        so_status = frappe.db.get_value(
            "Sales Order", self.sales_order, ["docstatus", "status"], as_dict=True
        )

        if not so_status:
            frappe.throw(_("Sales Order {0} not found").format(self.sales_order))

        if so_status.docstatus != 1:
            frappe.throw(_("Sales Order {0} must be submitted").format(self.sales_order))

        if so_status.status in ("Closed", "Cancelled"):
            frappe.throw(
                _("Cannot create Release Order for {0} Sales Order {1}").format(
                    so_status.status, self.sales_order
                )
            )

    def validate_release_quantities(self):
        """Validate release quantities for each item"""
        if not self.items:
            frappe.throw(_("At least one item is required"))

        has_qty = False
        errors = []

        for item in self.items:
            if flt(item.release_qty) > 0:
                has_qty = True

            # Release qty should not exceed pending qty
            if flt(item.release_qty) > flt(item.pending_qty):
                errors.append(
                    _("Row {0}: Release Qty ({1}) cannot exceed Pending Qty ({2}) for item {3}").format(
                        item.idx,
                        item.release_qty,
                        item.pending_qty,
                        item.item_code,
                    )
                )

            # Release qty should not be negative
            if flt(item.release_qty) < 0:
                errors.append(
                    _("Row {0}: Release Qty cannot be negative for item {1}").format(
                        item.idx, item.item_code
                    )
                )

        if errors:
            frappe.throw("<br>".join(errors))

        if not has_qty:
            frappe.throw(_("At least one item must have Release Qty > 0"))

    def calculate_totals(self):
        """Calculate total release qty"""
        self.total_qty = sum(flt(item.release_qty) for item in self.items)

    def on_submit(self):
        """Actions on submit"""
        pass

    def on_cancel(self):
        """Check for linked Delivery Notes before cancelling"""
        # Check if custom_release_order field exists in Delivery Note
        if not frappe.db.exists(
            "Custom Field",
            {"dt": "Delivery Note", "fieldname": "custom_release_order"},
        ):
            # Field doesn't exist yet, skip the check
            return

        # Check if any submitted DN exists
        linked_dns = frappe.get_all(
            "Delivery Note",
            filters={
                "custom_release_order": self.name,
                "docstatus": 1,
            },
            pluck="name",
        )

        if linked_dns:
            frappe.throw(
                _("Cannot cancel Release Order. Following Delivery Notes are linked: {0}").format(
                    ", ".join(linked_dns)
                )
            )


@frappe.whitelist()
def make_release_order(source_name, target_doc=None):
    """Create Release Order from Sales Order"""

    def set_missing_values(source, target):
        target.posting_date = frappe.utils.today()

    def update_item(source_doc, target_doc, source_parent):
        """Set quantity fields for each item"""
        target_doc.so_qty = flt(source_doc.qty)
        target_doc.delivered_qty = flt(source_doc.delivered_qty)
        target_doc.pending_qty = flt(source_doc.qty) - flt(source_doc.delivered_qty)
        target_doc.release_qty = target_doc.pending_qty  # Default to pending qty

    doclist = get_mapped_doc(
        "Sales Order",
        source_name,
        {
            "Sales Order": {
                "doctype": "Release Order",
                "field_map": {"name": "sales_order"},
                "validation": {"docstatus": ["=", 1]},
            },
            "Sales Order Item": {
                "doctype": "Release Order Item",
                "field_map": {
                    "name": "so_detail",
                    "warehouse": "warehouse",
                    "item_code": "item_code",
                    "item_name": "item_name",
                    "uom": "uom",
                },
                "condition": lambda d: flt(d.qty) > flt(d.delivered_qty),
                "postprocess": update_item,
            },
        },
        target_doc,
        set_missing_values,
    )

    return doclist


@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None):
    """Create Delivery Note from Release Order"""

    def set_missing_values(source, target):
        target.posting_date = frappe.utils.today()
        target.custom_release_order = source.name

    def update_item(source_doc, target_doc, source_parent):
        """Set qty and SO references for stock tracking"""
        target_doc.qty = flt(source_doc.release_qty)
        # Set SO references for ERPNext stock tracking
        target_doc.against_sales_order = source_parent.sales_order
        target_doc.so_detail = source_doc.so_detail

    # Get source doc for additional field mapping
    source = frappe.get_doc("Release Order", source_name)

    doclist = get_mapped_doc(
        "Release Order",
        source_name,
        {
            "Release Order": {
                "doctype": "Delivery Note",
                "field_map": {
                    "customer": "customer",
                    "customer_name": "customer_name",
                    "company": "company",
                },
                "validation": {"docstatus": ["=", 1]},
            },
            "Release Order Item": {
                "doctype": "Delivery Note Item",
                "field_map": {
                    "item_code": "item_code",
                    "item_name": "item_name",
                    "warehouse": "warehouse",
                    "uom": "uom",
                },
                "condition": lambda d: flt(d.release_qty) > 0,
                "postprocess": update_item,
            },
        },
        target_doc,
        set_missing_values,
    )

    return doclist


@frappe.whitelist()
def get_sales_order_items(sales_order):
    """Get Sales Order items with pending quantities for populating Release Order"""
    if not sales_order:
        return []

    so = frappe.get_doc("Sales Order", sales_order)

    items = []
    for item in so.items:
        pending_qty = flt(item.qty) - flt(item.delivered_qty)
        if pending_qty > 0:
            items.append(
                {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "uom": item.uom,
                    "warehouse": item.warehouse,
                    "so_detail": item.name,
                    "so_qty": item.qty,
                    "delivered_qty": item.delivered_qty,
                    "pending_qty": pending_qty,
                    "release_qty": pending_qty,
                }
            )

    return items


@frappe.whitelist()
def get_so_items_delivery_status(sales_order):
    """Get all Sales Order items with their current delivered_qty (for updating Release Order display)"""
    if not sales_order:
        return {}

    so = frappe.get_doc("Sales Order", sales_order)

    result = {}
    for item in so.items:
        result[item.name] = {
            "delivered_qty": flt(item.delivered_qty),
            "pending_qty": flt(item.qty) - flt(item.delivered_qty),
        }

    return result
