# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = [
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
        {"label": "Work Order", "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 200},
        {"label": "Material", "fieldname": "material", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": "Material Description", "fieldname": "material_desc", "fieldtype": "Data", "width": 180},
        {"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": "Order Qty", "fieldname": "order_qty", "fieldtype": "Float", "width": 100},
        {"label": "Production Qty", "fieldname": "production_qty", "fieldtype": "Float", "width": 120},
        {"label": "Pending Order Qty", "fieldname": "pending_order_qty", "fieldtype": "Float", "width": 120},
        {"label": "Component", "fieldname": "component", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": "Component Description", "fieldname": "component_desc", "fieldtype": "Data", "width": 180},
        {"label": "Com UOM", "fieldname": "com_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": "Required Qty", "fieldname": "required_qty", "fieldtype": "Float", "width": 100},
        {"label": "Actual Qty", "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
        {"label": "Difference Qty", "fieldname": "diff_qty", "fieldtype": "Float", "width": 120},
        {"label": "Req. %", "fieldname": "req_percent", "fieldtype": "Percent", "width": 80},
        {"label": "Act. %", "fieldname": "act_percent", "fieldtype": "Percent", "width": 80},
    ]

    data = []

    work_orders = frappe.get_all(
        "Work Order",
        filters={"status": "Completed"},
        fields=["name", "qty", "produced_qty", "production_item", "creation"]
    )

    for wo in work_orders:
        required_items = frappe.get_all(
            "Work Order Item",
            filters={"parent": wo.name},
            fields=["item_code", "description", "stock_uom", "required_qty"]
        )
        req_total = sum(itm.required_qty for itm in required_items)

        actual_items = frappe.get_all(
            "Work Order Item",
            filters={"parent": wo.name},
            fields=["item_code", "consumed_qty"]
        )
        
        actual_map = {a.item_code: a.consumed_qty for a in actual_items}
        
        actual_sum = sum(itm.consumed_qty for itm in actual_items)

        for req in required_items:
            actual_qty = actual_map.get(req.item_code, 0)
            diff_qty = actual_qty - req.required_qty

            row = {
                "work_order": wo.name,
                "material": wo.production_item,
                "material_desc": frappe.db.get_value("Item", wo.production_item, "description"),
                "uom": frappe.db.get_value("Item", wo.production_item, "stock_uom"),
                "component": req.item_code,
                "component_desc": req.description,
                "com_uom": frappe.db.get_value("Item", req.item_code, "stock_uom"),
                "order_qty": wo.qty,
                "pending_order_qty": wo.qty - wo.produced_qty,
                "production_qty": wo.produced_qty,
                "required_qty": req.required_qty,
                "actual_qty": actual_qty or "",
                "diff_qty": diff_qty,
                "posting_date": wo.creation.date(),
                "req_percent": (req.required_qty/req_total)*100,
                "act_percent": (actual_qty/actual_sum)*100,
            }
            data.append(row)

    return columns, data


