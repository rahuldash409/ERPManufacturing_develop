import frappe
from frappe import _
from frappe.utils import flt
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote


class CustomDeliveryNote(DeliveryNote):
    def validate(self):
        self.validate_qty_with_bundle()
        super().validate()

    def set_serial_and_batch_bundle(self, table_field="items"):
        """
        Override to skip bundle qty validation for incremental assignment.
        We have our own validation in validate_qty_with_bundle().
        """
        # Skip ERPNext's strict qty validation for items table
        # We allow item qty >= bundle qty for incremental bale assignment
        if table_field == "items":
            return
        # Call parent method for other tables (packed_items, etc.)
        super().set_serial_and_batch_bundle(table_field)

    def validate_qty_with_bundle(self):
        """
        Validate that item qty is not less than Serial and Batch Bundle qty.
        Allows incremental bale assignment when item qty is increased.
        """
        for item in self.items:
            if item.serial_and_batch_bundle:
                # Get the bundle's total qty
                bundle_qty = frappe.db.sql(
                    """
                    SELECT SUM(ABS(qty)) as total_qty
                    FROM `tabSerial and Batch Entry`
                    WHERE parent = %s
                    """,
                    item.serial_and_batch_bundle,
                    as_dict=True,
                )

                if bundle_qty and bundle_qty[0].total_qty:
                    bundle_total = flt(bundle_qty[0].total_qty)
                    item_qty = flt(item.qty)

                    # Allow item qty to be >= bundle qty (for incremental assignment)
                    # Only throw error if item qty < bundle qty (user trying to reduce qty)
                    if item_qty < bundle_total:
                        frappe.throw(
                            _(
                                "Row {0}: Cannot reduce quantity to {1} when Serial and Batch Bundle has {2}. "
                                "Please remove bales first to reduce quantity."
                            ).format(item.idx, item_qty, bundle_total)
                        )

    def on_cancel(self):
        self.unlink_bales_and_related_docs()
        super().on_cancel()

    def unlink_bales_and_related_docs(self):
        """Unlink Bales, Bales Creator and Stock Entry when DN is cancelled"""
        bales_list = self.get_linked_bales()

        for bale_name in bales_list:
            bale_data = frappe.db.get_value(
                "Bales",
                bale_name,
                ["bales_status", "source_document_type", "source_document", "material_consumption_entry"],
                as_dict=True,
            )

            if not bale_data:
                continue

            if bale_data.bales_status == "Dispatched":
                revert_status = "Packed Import" if bale_data.source_document_type == "Purchase Receipt" else "Packed In House"

                frappe.db.set_value(
                    "Bales",
                    bale_name,
                    {"bales_status": revert_status, "delivery_note": None},
                    update_modified=True,
                )

            if bale_data.source_document_type == "Bales Creator" and bale_data.source_document:
                self.unlink_bales_creator(bale_data.source_document)

            if bale_data.material_consumption_entry:
                self.unlink_stock_entry(bale_data.material_consumption_entry)

        self.delete_delivery_note_bales_doc()

    def get_linked_bales(self):
        """Get list of bales linked to this Delivery Note"""
        doc_name = frappe.db.get_value(
            "Delivery Note Bales", {"delivery_note": self.name}, "name"
        )
        if not doc_name:
            return []

        return frappe.get_all(
            "Delivery Note Bales Detail", filters={"parent": doc_name}, pluck="bale"
        )

    def unlink_bales_creator(self, bales_creator_name):
        """Clear stock_entry link from Bales Creator"""
        if frappe.db.exists("Bales Creator", bales_creator_name):
            frappe.db.set_value(
                "Bales Creator",
                bales_creator_name,
                "stock_entry",
                None,
                update_modified=True,
            )

    def unlink_stock_entry(self, stock_entry_name):
        """Clear custom_bales_creator link from Stock Entry"""
        if frappe.db.exists("Stock Entry", stock_entry_name):
            frappe.db.set_value(
                "Stock Entry",
                stock_entry_name,
                "custom_bales_creator",
                None,
                update_modified=True,
            )

    def delete_delivery_note_bales_doc(self):
        """Delete Delivery Note Bales document"""
        doc_name = frappe.db.get_value(
            "Delivery Note Bales", {"delivery_note": self.name}, "name"
        )
        if doc_name:
            frappe.delete_doc("Delivery Note Bales", doc_name, force=True)
