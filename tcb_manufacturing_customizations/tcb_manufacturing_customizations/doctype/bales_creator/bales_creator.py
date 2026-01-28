# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, format_date, today


class BalesCreator(Document):
    def validate(self):
        self.validate_items()
        self.calculate_total_qty()

    def before_submit(self):
        self.validate_no_existing_bales()

    def on_submit(self):
        self.create_opening_stock_bales()

    def on_cancel(self):
        self.cancel_opening_stock_bales()

    def validate_items(self):
        """Validate that items table has valid rows with qty > 0"""
        if not self.items:
            frappe.throw(_("At least one item row is required in Bales Creator"))

        for idx, item in enumerate(self.items, start=1):
            if not item.item_code:
                frappe.throw(_("Row {0}: Item Code is required").format(idx))

            if not item.warehouse:
                frappe.throw(_("Row {0}: Warehouse is required").format(idx))

            if flt(item.qty) <= 0:
                frappe.throw(_("Row {0}: Qty must be greater than zero").format(idx))

            # Validate qty matches Item.custom_bale_qty
            expected_qty = frappe.db.get_value(
                "Item", item.item_code, "custom_bale_qty"
            )
            if expected_qty and flt(item.qty) != flt(expected_qty):
                frappe.msgprint(
                    _(
                        "Row {0}: Qty {1} differs from Item's standard bale qty {2}"
                    ).format(idx, item.qty, expected_qty),
                    indicator="orange",
                    alert=True,
                )

    def validate_no_existing_bales(self):
        """Prevent duplicate bales creation if already created for this Bales Creator"""
        existing_bales = frappe.db.get_all(
            "Bales",
            filters={
                "source_document_type": "Bales Creator",
                "source_document": self.name,
                "docstatus": ["!=", 2],  # Not cancelled
            },
            pluck="name",
        )

        if existing_bales:
            frappe.throw(
                _("Bales have already been created for this Bales Creator: {0}").format(
                    ", ".join(existing_bales)
                )
            )

    def calculate_total_qty(self):
        """Calculate total qty from items table"""
        total = sum(flt(item.qty) for item in self.items) if self.items else 0
        self.total_qty = total

    def create_opening_stock_bales(self):
        """
        Create and SUBMIT Bales directly for Opening Stock.

        No Stock Entry is created - raw materials are not consumed.
        Bales are created and submitted immediately with status 'Packed In House'.
        """
        created_bales = []
        errors = []

        # Track in-flight batch consumption within this transaction
        in_flight_consumption = {}

        for idx, item in enumerate(self.items, start=1):
            try:
                bales_id, batch_allocations = self._create_single_bale(
                    item, idx, in_flight_consumption
                )
                if bales_id:
                    # Submit the Bale immediately
                    bales_doc = frappe.get_doc("Bales", bales_id)
                    bales_doc.submit()
                    if self.get("bales_source") == "Import":
                        # bales_doc.db_set("bales_status", "Packed Import", commit=True, update_modified=False)
                        # Set status to 'Packed In House'
                        frappe.db.set_value(
                            "Bales",
                            bales_id,
                            "bales_status",
                            "Packed Import",
                            update_modified=False,
                        )
                    else:
                        # Set status to 'Packed In House'
                        frappe.db.set_value(
                            "Bales",
                            bales_id,
                            "bales_status",
                            "Packed In House",
                            update_modified=False,
                        )
                        # bales_doc.db_set("bales_status", "Packed In House", commit=True, update_modified=False)

                    created_bales.append(bales_id)

                    # Update the item row with the created bales_id
                    frappe.db.set_value(
                        "Bales Creator Item",
                        item.name,
                        "bales_id",
                        bales_id,
                        update_modified=False,
                    )

                    # Update in-flight consumption with this Bale's allocations
                    for alloc in batch_allocations:
                        key = (item.item_code, item.warehouse, alloc["batch"])
                        in_flight_consumption[key] = (
                            in_flight_consumption.get(key, 0) + alloc["qty_taken"]
                        )

            except Exception as e:
                errors.append(_("Row {0}: {1}").format(idx, str(e)))

        # If any errors occurred, rollback all created bales and throw error
        if errors:
            for bales_id in created_bales:
                try:
                    bales_doc = frappe.get_doc("Bales", bales_id)
                    if bales_doc.docstatus == 1:
                        bales_doc.flags.ignore_links = True
                        bales_doc.cancel()
                    frappe.delete_doc(
                        "Bales", bales_id, force=True, ignore_permissions=True
                    )
                except Exception:
                    pass

            frappe.throw(
                _("Failed to create Opening Stock Bales. Errors: {0}").format(
                    "<br>".join(errors)
                )
            )

        if created_bales:
            frappe.msgprint(
                _(
                    "Successfully created and submitted {0} Opening Stock Bales: {1}"
                ).format(len(created_bales), ", ".join(created_bales)),
                indicator="green",
                alert=True,
            )

    def _create_single_bale(self, item_row, row_idx, in_flight_consumption=None):
        """
        Create a single Bale document in DRAFT mode.
        Does NOT submit the Bale or create ledger entries.

        Args:
            item_row: Bales Creator Item row
            row_idx: Row index for error messages
            in_flight_consumption: Dict tracking batch qty already allocated
                                   to previous Bales in this transaction.
                                   Key: (item_code, warehouse, batch) -> qty_consumed

        Returns:
            Tuple of (bales_name, batch_allocations_list) if successful.
            batch_allocations_list is used to update in_flight_consumption.
        """
        item_code = item_row.item_code
        warehouse = item_row.warehouse
        qty = flt(item_row.qty)

        # Get Manufacture source
        # bales_source = get_manufacture_bales_source()
        bales_source = self.get("bales_source")

        material_receipts = self.get("material_receipts") or []
        # Extract stock_entry names from child table rows
        voucher_nos = tuple([mr.stock_entry for mr in material_receipts if mr.stock_entry]) if material_receipts else ()

        # Fetch available batches in FIFO order, considering in-flight consumption - PKG Item Batches
        batches = get_available_batches_fifo(
            item_code,
            warehouse,
            qty,
            in_flight_consumption,
            voucher_nos=voucher_nos,
        )

        frappe.log_error("Batches Found", f"Vouchers : {voucher_nos}\nBatches : {batches}")

        if not batches:
            frappe.throw(
                _("Row {0}: No batches available for item {1} in warehouse {2}").format(
                    row_idx, item_code, warehouse
                )
            )

        # Calculate total qty available from batches
        total_available = sum(b["qty_taken"] for b in batches)
        if total_available < qty:
            frappe.throw(
                _(
                    "Row {0}: Insufficient batch quantity. Required: {1}, Available: {2}"
                ).format(row_idx, qty, total_available)
            )

        # Create Bales document
        bales_doc = frappe.new_doc("Bales")
        bales_doc.item = item_code
        bales_doc.warehouse = warehouse
        bales_doc.bale_qty = qty
        bales_doc.bales_source = bales_source

        bales_doc.source_document_type = "Bales Creator"
        bales_doc.source_document = self.name
        bales_doc.posting_date = today()

        # Fill packed_items table
        for batch_data in batches:
            bales_doc.append(
                "packed_items",
                {
                    "batch_no": batch_data["batch"],
                    "sub_batch": batch_data["sub_batch"],
                    "qty": batch_data["qty_taken"],
                    "item_code": item_code,
                    "warehouse": warehouse,
                },
            )

        sg_item_code = self.get("sg_item_code")
        sg_warehouse = self.get("sg_warehouse")
        if sg_item_code and False:
            # Fetch available batches in FIFO order, considering in-flight consumption - SG Item Batches
            batches = get_available_batches_fifo(
                sg_item_code,
                sg_warehouse,
                qty,
                in_flight_consumption,
                voucher_nos=voucher_nos,
            )

            frappe.log_error("Batches Found", f"Vouchers : {voucher_nos}\nBatches : {batches}")

            if not batches:
                frappe.throw(
                    _("Row {0}: No batches available for item {1} in warehouse {2}").format(
                        row_idx, sg_item_code, sg_warehouse
                    )
                )

            # Calculate total qty available from batches
            total_available = sum(b["qty_taken"] for b in batches)
            if total_available < qty:
                frappe.throw(
                    _(
                        "Row {0}: Insufficient batch quantity. Required: {1}, Available: {2}"
                    ).format(row_idx, qty, total_available)
                )

            # Fill batches_used table
            for batch_data in batches:
                bales_doc.append(
                    "batches_used",
                    {
                        "batch": batch_data["batch"],
                        "sub_batch": batch_data["sub_batch"],
                        "qty_taken": batch_data["qty_taken"],
                        "item": sg_item_code,
                        "warehouse": sg_warehouse,
                    },
                )

        # Insert the Bales document in Draft mode only
        # Bales will be submitted when the linked Stock Entry is submitted
        bales_doc.insert(ignore_permissions=True)

        return bales_doc.name, batches

    def cancel_opening_stock_bales(self):
        """
        Cancel all submitted Bales created for Opening Stock.

        Since no Stock Entry exists for Opening Stock, we directly cancel the Bales.
        """
        # Get all submitted Bales linked to this Bales Creator
        bales_to_cancel = frappe.db.get_all(
            "Bales",
            filters={
                "source_document_type": "Bales Creator",
                "source_document": self.name,
                "docstatus": 1,  # Submitted bales
            },
            pluck="name",
        )

        if not bales_to_cancel:
            # Also check for draft bales and delete them
            self._delete_draft_bales()
            return

        # Check for dispatched bales - block if any are dispatched
        dispatched_bales = []
        for bales_name in bales_to_cancel:
            status = frappe.db.get_value("Bales", bales_name, "bales_status")
            if status == "Dispatched":
                dispatched_bales.append(bales_name)

        if dispatched_bales:
            frappe.throw(
                _(
                    "Cannot cancel Bales Creator. The following Bales have been dispatched: "
                    "{0}. Please cancel the Delivery Note first."
                ).format(", ".join(dispatched_bales))
            )

        cancelled_bales = []
        errors = []

        # Set flag to allow Bales cancellation
        frappe.flags.opening_stock_bale_cancel = True

        try:
            for bales_name in bales_to_cancel:
                try:
                    bales_doc = frappe.get_doc("Bales", bales_name)
                    bales_doc.flags.ignore_links = True
                    bales_doc.cancel()
                    cancelled_bales.append(bales_name)
                except Exception as e:
                    errors.append(f"{bales_name}: {str(e)}")
                    frappe.log_error(
                        message=str(e), title="Opening Stock Bales Cancel Error"
                    )
        finally:
            frappe.flags.opening_stock_bale_cancel = False

        if cancelled_bales:
            frappe.msgprint(
                _("Cancelled {0} Opening Stock Bales: {1}").format(
                    len(cancelled_bales), ", ".join(cancelled_bales)
                ),
                indicator="orange",
                alert=True,
            )

        if errors:
            frappe.throw(
                _("Failed to cancel some Bales: {0}").format("<br>".join(errors))
            )

    def _delete_draft_bales(self):
        """Delete draft Bales linked to this Bales Creator"""
        draft_bales = frappe.db.get_all(
            "Bales",
            filters={
                "source_document_type": "Bales Creator",
                "source_document": self.name,
                "docstatus": 0,  # Draft bales only
            },
            pluck="name",
        )

        deleted_count = 0
        for bales_name in draft_bales:
            try:
                frappe.delete_doc(
                    "Bales", bales_name, force=True, ignore_permissions=True
                )
                deleted_count += 1
            except Exception as e:
                frappe.log_error(
                    f"Error deleting draft Bales {bales_name}: {str(e)}",
                    "Bales Creator Cancel Error",
                )

        if deleted_count:
            frappe.msgprint(
                _("Deleted {0} draft Bales").format(deleted_count),
                indicator="orange",
                alert=True,
            )


def get_available_batches_fifo(
    item_code, warehouse, required_qty, in_flight_consumption=None, voucher_nos=()
):
    """
    Fetch batches in FIFO order (oldest first by creation date) with remaining qty.
    Remaining qty = Stock qty - Already consumed in Bales Ledger Entry - In-flight consumption

    Args:
        item_code: Item code to fetch batches for
        warehouse: Warehouse to check stock
        required_qty: Qty required for the Bale
        in_flight_consumption: Dict tracking batch qty already allocated
                               to previous Bales in current transaction.
                               Key: (item_code, warehouse, batch) -> qty_consumed
    """
    required_qty = flt(required_qty)
    in_flight_consumption = in_flight_consumption or {}

    # Get stock qty per batch from Stock Ledger Entry via Serial and Batch Bundle
    if voucher_nos:
        stock_batches = frappe.db.sql(
            """
            SELECT
                b.name as batch,
                b.custom_sub_batch as sub_batch,
                b.creation,
                sle.voucher_no as stock_entry,
                SUM(sle.actual_qty) as stock_qty
            FROM `tabBatch` b
            INNER JOIN `tabSerial and Batch Entry` sbe ON sbe.batch_no = b.name
            INNER JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sbe.parent
            WHERE sle.item_code = %s
            AND sle.warehouse = %s
            AND sle.is_cancelled = 0
            AND sle.voucher_type = "Stock Entry"
            AND sle.voucher_no in %s
            GROUP BY b.name
            HAVING stock_qty > 0
            ORDER BY b.creation ASC
        """,
            (item_code, warehouse, voucher_nos),
            as_dict=True,
        )
    else:
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

    # Get already consumed qty from Bales Ledger Entry (committed to DB)
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
        # Qty consumed from Bales Ledger Entry (committed, submitted Bales)
        ledger_consumed_qty = consumed_map.get(batch.batch, 0)

        # Qty consumed in-flight (allocated to previous Bales in this transaction)
        in_flight_key = (item_code, warehouse, batch.batch)
        in_flight_qty = in_flight_consumption.get(in_flight_key, 0)

        # Total consumed = committed + in-flight
        total_consumed = ledger_consumed_qty + in_flight_qty
        available = flt(batch.stock_qty) - total_consumed

        if available <= 0:
            continue

        qty_to_take = min(available, remaining_required)
        result.append(
            {
                "batch": batch.batch,
                "sub_batch": batch.sub_batch,
                "qty_taken": qty_to_take,
                "stock_entry": batch.get("stock_entry", "")
            }
        )

        remaining_required -= qty_to_take
        if remaining_required <= 0:
            break

    return result


def get_bom_raw_materials_for_bale_item(bale_item_code, bale_qty):
    """
    Find BOMs where the bale item is used as raw material and calculate
    the OTHER raw material quantities needed (excluding bale item itself).

    BUSINESS RULE:
    - Search for BOM where bale_item_code exists as a RAW MATERIAL
    - Return all OTHER raw materials from that BOM (exclude the bale_item itself)
    - The bale item itself must NOT be issued in Stock Entry (it's being packed into bales)
    - Only the packaging/other materials need to be consumed

    Example:
    - BOM: Packed Product → [Bale Item (7500 kg), Packaging (10 pcs), Thread (5 kg)]
    - When creating Bale of 7500 kg, we consume Packaging (10 pcs) + Thread (5 kg)
    - Bale Item itself is NOT consumed (it's what we're packing)

    Returns list of raw materials with required quantities.
    """
    # Find BOMs that have this bale item as a raw material
    bom_items = frappe.get_all(
        "BOM Item", filters={"item_code": bale_item_code}, fields=["parent", "qty"]
    )

    if not bom_items:
        return []

    raw_materials = {}

    for bom_item in bom_items:
        bom = frappe.get_doc("BOM", bom_item.parent)

        # Skip if BOM is not active or not submitted
        if bom.is_active != 1 or bom.docstatus != 1:
            continue

        # Calculate ratio: how many BOMs worth of the bale item we're creating
        bom_ratio = flt(bale_qty) / flt(bom_item.qty) if flt(bom_item.qty) else 0

        # Get all raw materials from this BOM (EXCEPT the bale item itself)
        for raw_material in bom.items:
            # CRITICAL: Skip the bale item - it must NOT be issued
            # The bale item is what we're packing, not consuming
            if raw_material.item_code == bale_item_code:
                continue

            required_qty = flt(raw_material.qty) * bom_ratio

            if raw_material.item_code not in raw_materials:
                raw_materials[raw_material.item_code] = {
                    "item_code": raw_material.item_code,
                    "item_name": frappe.db.get_value(
                        "Item", raw_material.item_code, "item_name"
                    ),
                    "required_qty": 0,
                    "uom": raw_material.uom,
                }

            raw_materials[raw_material.item_code]["required_qty"] += required_qty

    return list(raw_materials.values())


def get_manufacture_bales_source():
    """
    Get the Bales Source record for Manufacture.
    Bales Creator is exclusively for Manufacture flow.

    Searches for Bales Source with name containing 'Manufactur' (case-insensitive)
    to handle variations like 'Manufacture', 'Manufactured', etc.
    """
    # Try common variations for manufacture source
    for source_name in ["Manufacture", "Manufactured", "Manufacturing"]:
        if frappe.db.exists("Bales Source", source_name):
            return source_name

    # Fallback: Search for any source containing 'manufactur'
    manufacture_source = frappe.db.get_value(
        "Bales Source", {"bales_source": ["like", "%Manufactur%"]}, "name"
    )

    if manufacture_source:
        return manufacture_source

    # If no manufacture source found, return None (field is optional)
    return None


@frappe.whitelist()
def get_item_bale_qty(item_code):
    """Get the custom_bale_qty from Item doctype"""
    if not item_code:
        return 0

    bale_qty = frappe.db.get_value("Item", item_code, "custom_bale_qty")
    return flt(bale_qty) or 0
