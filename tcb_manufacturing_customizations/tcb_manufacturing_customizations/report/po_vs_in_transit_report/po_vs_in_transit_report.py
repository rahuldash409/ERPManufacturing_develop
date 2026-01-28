# Copyright (c) 2026, Rahul Dash and contributors
# For license information, please see license.txt

# import frappe


import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": _("Purchase Order"),
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 150
        },
        {
            "label": _("Item"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "label": _("PO Qty"),
            "fieldname": "po_qty",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": _("Total In Transit Qty"),
            "fieldname": "pr_qty",
            "fieldtype": "Float",
            "width": 140
        }
    ]


def get_data(filters):
    if not filters:
        return []

    po_list = get_purchase_orders(filters)
    if not po_list:
        return []

    po_items_map = get_po_items(po_list)
    pr_items = get_pr_items(po_list)

    received_map = {}
    extra_items_map = {}

    # Consolidate PR quantities
    for pr in pr_items:
        po = pr.purchase_order
        item = pr.item_code
        qty = pr.qty

        if item in po_items_map.get(po, {}):
            received_map.setdefault(po, {}).setdefault(item, 0)
            received_map[po][item] += qty
        else:
            extra_items_map.setdefault(po, {}).setdefault(item, 0)
            extra_items_map[po][item] += qty

    data = []

    # PO Items (original PO items)
    for po, items in po_items_map.items():
        for item_code, po_qty in items.items():
            data.append({
                "purchase_order": po,
                "item_code": item_code,
                "po_qty": po_qty,
                "pr_qty": received_map.get(po, {}).get(item_code, 0)
            })

    # Extra Items (not present in PO)
    for po, items in extra_items_map.items():
        for item_code, qty in items.items():
            data.append({
                "purchase_order": po,
                "item_code": item_code,
                "po_qty": 0,
                "pr_qty": qty
            })

    return data


def get_purchase_orders(filters):
    conditions = {
        "docstatus": 1
    }

    if filters.get("supplier"):
        conditions["supplier"] = filters.supplier

    if filters.get("from_date") and filters.get("to_date"):
        conditions["transaction_date"] = ["between", [filters.from_date, filters.to_date]]

    return frappe.get_all(
        "Purchase Order",
        filters=conditions,
        fields=["name"]
    )


def get_po_items(po_list):
    po_names = [po.name for po in po_list]

    items = frappe.get_all(
        "Purchase Order Item",
        filters={
            "parent": ["in", po_names]
        },
        fields=["parent", "item_code", "qty"]
    )

    po_item_map = {}
    for item in items:
        po_item_map.setdefault(item.parent, {})
        po_item_map[item.parent].setdefault(item.item_code, 0)
        po_item_map[item.parent][item.item_code] += item.qty

    return po_item_map


def get_pr_items(po_list):
    po_names = [po.name for po in po_list]
    
    pr_list = get_pr(po_list)
    
 
    return frappe.get_all(
        "Purchase Receipt Item",
        filters={
            "parent":["in",pr_list]
        },
        fields=[
            "purchase_order",
            "item_code",
            "qty"
        ]
    )
    
    
def get_pr(po_list):
    po_names = [po.name for po in po_list]
    
    prs =  frappe.get_all(
        "Purchase Receipt",
        filters={
            "docstatus":0,
            "custom_purchase_order":["in",po_names]
        },
        fields=["name"]
    )
    
    return [pr.name for pr in prs]