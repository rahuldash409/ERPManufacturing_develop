import json
import math
import traceback
from copy import deepcopy
import math

import frappe
from erpnext.manufacturing.doctype.bom.bom import \
    get_children as get_bom_children
from erpnext.manufacturing.doctype.production_plan.production_plan import (
    ProductionPlan, get_items_for_material_requests)
from erpnext.stock.stock_balance import get_ordered_qty, get_planned_qty
from frappe import _
from frappe.query_builder.functions import IfNull, Sum
from frappe.utils import flt

from tcb_manufacturing_customizations.utils.stock import get_item_available_qty


@frappe.whitelist()
def get_bin_details(row, company, for_warehouse=None, all_warehouse=False):
    if isinstance(row, str):
        row = frappe._dict(json.loads(row))

    bin = frappe.qb.DocType("Bin")
    wh = frappe.qb.DocType("Warehouse")

    subquery = frappe.qb.from_(wh).select(wh.name).where(wh.company == company)

    warehouse = ""
    if not all_warehouse:
        warehouse = (
            for_warehouse or row.get("source_warehouse") or row.get("default_warehouse")
        )

    if warehouse:
        lft, rgt = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"])
        subquery = subquery.where(
            (wh.lft >= lft) & (wh.rgt <= rgt) & (wh.name == bin.warehouse)
        )

    query = (
        frappe.qb.from_(bin)
        .select(
            bin.warehouse,
            IfNull(Sum(bin.projected_qty), 0).as_("projected_qty"),
            IfNull(Sum(bin.actual_qty), 0).as_("actual_qty"),
            IfNull(Sum(bin.ordered_qty), 0).as_("ordered_qty"),
            IfNull(Sum(bin.reserved_qty_for_production), 0).as_(
                "reserved_qty_for_production"
            ),
            IfNull(Sum(bin.planned_qty), 0).as_("planned_qty"),
        )
        .where((bin.item_code == row["item_code"]) & (bin.warehouse.isin(subquery)))
        .groupby(bin.item_code, bin.warehouse)
    )

    return query.run(as_dict=True)


def get_sub_assembly_items(
    sub_assembly_items,
    bin_details,
    bom_no,
    bom_data,
    to_produce_qty,
    company,
    warehouse=None,
    indent=0,
    skip_available_sub_assembly_item=False,
):
    data = get_bom_children(parent=bom_no)
    for d in data:
        if d.expandable:
            parent_item_code = frappe.get_cached_value("BOM", bom_no, "item")
            stock_qty = (d.stock_qty / d.parent_bom_qty) * flt(to_produce_qty)

            if (
                skip_available_sub_assembly_item
                and d.item_code not in sub_assembly_items
            ):
                bin_details.setdefault(
                    d.item_code, get_bin_details(d, company, for_warehouse=warehouse)
                )

                for _bin_dict in bin_details[d.item_code]:
                    if _bin_dict.projected_qty > 0:
                        if _bin_dict.projected_qty >= stock_qty:
                            _bin_dict.projected_qty -= stock_qty
                            stock_qty = 0
                            continue
                        else:
                            stock_qty = stock_qty - _bin_dict.projected_qty
                            sub_assembly_items.append(d.item_code)
            elif warehouse:
                bin_details.setdefault(
                    d.item_code, get_bin_details(d, company, for_warehouse=warehouse)
                )

            if stock_qty > 0:
                bom_data.append(
                    frappe._dict(
                        {
                            "actual_qty": (
                                bin_details[d.item_code][0].get("actual_qty", 0)
                                if bin_details.get(d.item_code)
                                else 0
                            ),
                            "parent_item_code": parent_item_code,
                            "description": d.description,
                            "production_item": d.item_code,
                            "item_name": d.item_name,
                            "stock_uom": d.stock_uom,
                            "uom": d.stock_uom,
                            "bom_no": d.value,
                            "is_sub_contracted_item": d.is_sub_contracted_item,
                            "bom_level": indent,
                            "indent": indent,
                            "stock_qty": stock_qty,
                        }
                    )
                )

                if d.value:
                    get_sub_assembly_items(
                        sub_assembly_items,
                        bin_details,
                        d.value,
                        bom_data,
                        stock_qty,
                        company,
                        warehouse,
                        indent=indent + 1,
                        skip_available_sub_assembly_item=skip_available_sub_assembly_item,
                    )


class CustomProductionPlan(ProductionPlan):
    def get_available_qty(self, item_code, warehouse):
        """
        Override to customize available quantity calculation
        """
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

    def get_so_qty(self, item_code, warehouse):
        so_qty = 0
        return so_qty

    def get_wo_remaining_qty(self, item_code, warehouse):
        wo_remaining_qty = 0
        woi = frappe.qb.DocType("Work Order Item")

        query = (
            frappe.qb.from_(woi)
            .select(
                woi.parent.as_("work_order"),
                woi.name,
                woi.item_code,
                woi.warehouse,
                IfNull(woi.required_qty, 0).as_("required_qty"),
                IfNull(woi.transferred_qty, 0).as_("transferred_qty"),
                IfNull(woi.consumed_qty, 0).as_("consumed_qty"),
                IfNull(woi.returned_qty, 0).as_("returned_qty"),
            )
            .where((woi.item_code == item_code) & (woi.warehouse == warehouse))
            .groupby(woi.item_code, woi.warehouse)
        )

        records = query.run(as_dict=True)
        required_qty = sum([record.get("required_qty") for record in records])
        transferred_qty = sum([record.get("transferred_qty") for record in records])
        consumed_qty = sum([record.get("consumed_qty") for record in records])
        returned_qty = sum([record.get("returned_qty") for record in records])
        wo_remaining_qty = required_qty - consumed_qty
        # wo_remaining_qty = required_qty - (consumed_qty - returned_qty)

        return wo_remaining_qty

    @frappe.whitelist()
    def get_items(self):
        super().get_items()
        frappe.log_error("PO Items", self.po_items)
        po_items = deepcopy(self.po_items)
        try:
            new_items = []
            for item in po_items:
                available_qty = self.get_available_qty(item.item_code, item.warehouse)
                po_qty = get_ordered_qty(item.item_code, item.warehouse)
                wo_qty = get_planned_qty(item.item_code, item.warehouse)

                item.custom_original_qty = item.get("planned_qty")
                actual_available_qty = available_qty + po_qty - wo_qty
                planned_qty = item.get("planned_qty")
                if actual_available_qty < planned_qty:
                    item.planned_qty = planned_qty - actual_available_qty
                else:
                    item.planned_qty = 0

                frappe.log_error(
                    "Current Production Plan Logs",
                    f"Item: {item.item_code}, Available: {available_qty}, PO Qty: {po_qty}, WO Qty: {wo_qty}, Planned Qty: {item.planned_qty}",
                )
                new_items.append(item)
            self.po_items = new_items
            frappe.log_error("Modified PO Items", [x.as_dict() for x in self.po_items])

            return new_items
        except Exception:
            frappe.log_error(
                "Error in CustomProductionPlan.get_items",
                traceback.format_exc(),
            )
            return po_items

    @frappe.whitelist()
    def get_sub_assembly_items(self, manufacturing_type=None):
        "Fetch sub assembly items and optionally combine them."
        self.sub_assembly_items = []
        sub_assembly_items_store = (
            []
        )  # temporary store to process all subassembly items
        bin_details = frappe._dict()

        for row in self.po_items:
            if (
                self.skip_available_sub_assembly_item
                and not self.sub_assembly_warehouse
            ):
                frappe.throw(
                    _("Row #{0}: Please select the Sub Assembly Warehouse").format(
                        row.idx
                    )
                )

            if not row.item_code:
                frappe.throw(
                    _("Row #{0}: Please select Item Code in Assembly Items").format(
                        row.idx
                    )
                )

            if not row.bom_no:
                frappe.throw(
                    _("Row #{0}: Please select the BOM No in Assembly Items").format(
                        row.idx
                    )
                )

            bom_data = []

            get_sub_assembly_items(
                [item.production_item for item in sub_assembly_items_store],
                bin_details,
                row.bom_no,
                bom_data,
                row.planned_qty,
                self.company,
                warehouse=self.sub_assembly_warehouse,
                skip_available_sub_assembly_item=self.skip_available_sub_assembly_item,
            )
            self.set_sub_assembly_items_based_on_level(
                row, bom_data, manufacturing_type
            )
            sub_assembly_items_store.extend(bom_data)

        if not sub_assembly_items_store and self.skip_available_sub_assembly_item:
            message = (
                _(
                    "As there are sufficient Sub Assembly Items, Work Order is not required for Warehouse {0}."
                ).format(self.sub_assembly_warehouse)
                + "<br><br>"
            )
            message += _(
                "If you still want to proceed, please disable 'Skip Available Sub Assembly Items' checkbox."
            )

            frappe.msgprint(message, title=_("Note"))

        if self.combine_sub_items:
            # Combine subassembly items
            sub_assembly_items_store = self.combine_subassembly_items(
                sub_assembly_items_store
            )

        for idx, row in enumerate(sub_assembly_items_store):
            row.qty = math.ceil(row.qty)
            row.idx = idx + 1
            self.append("sub_assembly_items", row)

        self.set_default_supplier_for_subcontracting_order()

    def set_sub_assembly_items_based_on_level(
        self, row, bom_data, manufacturing_type=None
    ):
        "Modify bom_data, set additional details."
        is_group_warehouse = frappe.db.get_value(
            "Warehouse", self.sub_assembly_warehouse, "is_group"
        )

        for data in bom_data:
            data.qty = data.stock_qty
            data.production_plan_item = row.name
            data.schedule_date = row.planned_start_date
            data.type_of_manufacturing = manufacturing_type or (
                "Subcontract" if data.is_sub_contracted_item else "In House"
            )

            if not is_group_warehouse:
                data.fg_warehouse = self.sub_assembly_warehouse

    def set_default_supplier_for_subcontracting_order(self):
        items = [
            d.production_item
            for d in self.sub_assembly_items
            if d.type_of_manufacturing == "Subcontract"
        ]

        if not items:
            return

        default_supplier = frappe._dict(
            frappe.get_all(
                "Item Default",
                fields=["parent", "default_supplier"],
                filters={"parent": ("in", items), "default_supplier": ("is", "set")},
                as_list=1,
            )
        )

        if not default_supplier:
            return

        for row in self.sub_assembly_items:
            if row.type_of_manufacturing != "Subcontract":
                continue

            row.supplier = default_supplier.get(row.production_item)

    def combine_subassembly_items(self, sub_assembly_items_store):
        "Aggregate if same: Item, Warehouse, Inhouse/Outhouse Manu.g, BOM No."
        key_wise_data = {}
        for row in sub_assembly_items_store:
            key = (
                row.get("production_item"),
                row.get("fg_warehouse"),
                row.get("bom_no"),
                row.get("type_of_manufacturing"),
            )
            if key not in key_wise_data:
                # intialise (item, wh, bom no, man.g type) wise dict
                key_wise_data[key] = row
                continue

            existing_row = key_wise_data[key]
            if existing_row:
                # if row with same (item, wh, bom no, man.g type) key, merge
                existing_row.qty += flt(row.qty)
                existing_row.stock_qty += flt(row.stock_qty)
                existing_row.bom_level = max(existing_row.bom_level, row.bom_level)
                continue
            else:
                # add row with key
                key_wise_data[key] = row

        sub_assembly_items_store = [
            key_wise_data[key] for key in key_wise_data
        ]  # unpack into single level list
        return sub_assembly_items_store

    def all_items_completed(self):
        all_items_produced = all(
            flt(d.planned_qty) - flt(d.produced_qty) < 0.000001 for d in self.po_items
        )
        if not all_items_produced:
            return False

        wo_status = frappe.get_all(
            "Work Order",
            filters={
                "production_plan": self.name,
                "status": ("not in", ["Closed", "Stopped"]),
                "docstatus": ("<", 2),
            },
            fields="status",
            pluck="status",
        )
        all_work_orders_completed = all(s == "Completed" for s in wo_status)
        return all_work_orders_completed


@frappe.whitelist()
def get_items_for_material_requests_override(
    doc, warehouses=None, get_parent_warehouse_data=None
):
    mr_items = get_items_for_material_requests(
        doc, warehouses=warehouses, get_parent_warehouse_data=get_parent_warehouse_data
    )
    frappe.log_error("Original MR Items", mr_items)
    new_mr_items = []
    if mr_items:
        for item in mr_items:
            new_quantity = item.get("quantity") - get_item_available_qty(
                item.get("item_code"), item.get("warehouse"), required_qty = item.get("quantity")
            )
            item["custom_quantity"] = item.get("quantity")
            item["quantity"] = math.ceil(new_quantity)
            if new_quantity > 0:
                new_mr_items.append(item)
    return new_mr_items
