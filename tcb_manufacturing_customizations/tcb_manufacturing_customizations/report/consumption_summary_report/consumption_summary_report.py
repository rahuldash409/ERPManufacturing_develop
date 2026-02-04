# Copyright (c) 2026, rahul.dash@spplgroup.com and contributors
# For license information, please see license.txt

# import frappe
import frappe


ALLOWED_ITEM_GROUPS = [
    "ink",
    "solvent/mixers",
    "laminated circular fabric",
    "laminated circular printed fabric",
    "laminated flat fabric",
    "laminated flat printed fabric",
    "laminated flat printed slited fabric",
    "laminated flat slited fabric",
]


def execute(filters=None):
    if not filters:
        return [], []

    columns = get_columns()
    data = get_data(filters)
    return columns, data


# --------------------------------------------------
# Columns
# --------------------------------------------------
def get_columns():
    return [
        {
            "label": "Item",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 260,
        },
        {
            "label": "UOM",
            "fieldname": "uom",
            "fieldtype": "Data",
            "width": 80,
        },
        {
            "label": "Item Group",
            "fieldname": "item_group",
            "fieldtype": "Data",
            "width": 220,
        },
        {
            "label": "Opening Qty",
            "fieldname": "opening_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": "Receipt Qty",
            "fieldname": "receipt_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": "Consumption Qty",
            "fieldname": "consumption_qty",
            "fieldtype": "Float",
            "width": 150,
        },
        {
            "label": "Closing Qty",
            "fieldname": "closing_qty",
            "fieldtype": "Float",
            "width": 120,
        },
    ]


# --------------------------------------------------
# Data Builder (Item-wise + Grouped + Subtotals)
# --------------------------------------------------
def get_data(filters):
    data = []

    items = get_items()

    group_order_map = {g: i for i, g in enumerate(ALLOWED_ITEM_GROUPS)}
    items = sorted(items, key=lambda x: (group_order_map.get(x.item_group, 999), x.name))

    current_group = None
    g_open = g_receipt = g_consume = g_close = 0

    for item in items:
        item_code = item.name
        item_group = item.item_group
        uom = item.stock_uom

        # ---------- New Group ----------
        if current_group != item_group:
            if current_group:
                data.append({
                    "item_code": f"{current_group.upper()} TOTAL",
                    "opening_qty": g_open,
                    "receipt_qty": g_receipt,
                    "consumption_qty": g_consume,
                    "closing_qty": g_close,
                })
                data.append({})

            data.append({
                "item_code": item_group.upper(),
            })

            g_open = g_receipt = g_consume = g_close = 0
            current_group = item_group

        # ---------- Calculations ----------
        opening = get_opening_qty(item_code, filters)
        receipt, consumption = get_movement_qty(item_code, filters)
        closing = opening + receipt - consumption

        if opening == receipt == consumption == closing == 0:
            continue

        data.append({
            "item_code": f"  {item_code}",
            "uom": uom,
            "item_group": item_group,
            "opening_qty": opening,
            "receipt_qty": receipt,
            "consumption_qty": consumption,
            "closing_qty": closing,
        })

        g_open += opening
        g_receipt += receipt
        g_consume += consumption
        g_close += closing

    # ---------- Last Group Total ----------
    if current_group:
        data.append({
            "item_code": f"{current_group.upper()} TOTAL",
            "opening_qty": g_open,
            "receipt_qty": g_receipt,
            "consumption_qty": g_consume,
            "closing_qty": g_close,
        })

    return data


# --------------------------------------------------
# Items (with UOM)
# --------------------------------------------------
def get_items():
    return frappe.get_all(
        "Item",
        filters={
            "item_group": ["in", ALLOWED_ITEM_GROUPS],
            "disabled": 0,
        },
        fields=["name", "item_group", "stock_uom"],
    )


# --------------------------------------------------
# Opening Stock (ALL warehouses)
# --------------------------------------------------
def get_opening_qty(item_code, filters):
    res = frappe.db.sql(
        """
        SELECT SUM(qty_after_transaction) AS opening_qty
        FROM (
            SELECT warehouse, qty_after_transaction
            FROM `tabStock Ledger Entry`
            WHERE item_code = %(item_code)s
              AND posting_date < %(from_date)s
            ORDER BY posting_date DESC, posting_time DESC, creation DESC
        ) t
        """,
        {
            "item_code": item_code,
            "from_date": filters["from_date"],
        },
        as_dict=True,
    )

    return res[0]["opening_qty"] or 0


# --------------------------------------------------
# Receipt (Purchase + Production) & True Consumption
# --------------------------------------------------
def get_movement_qty(item_code, filters):

    # -------- REAL RECEIPT --------
    receipt_res = frappe.db.sql(
        """
        SELECT SUM(sle.actual_qty) AS receipt_qty
        FROM `tabStock Ledger Entry` sle
        WHERE sle.item_code = %(item_code)s
          AND sle.actual_qty > 0
          AND sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND (
                sle.voucher_type = 'Purchase Receipt'
                OR (
                    sle.voucher_type = 'Stock Entry'
                    AND EXISTS (
                        SELECT 1
                        FROM `tabStock Entry` se
                        WHERE se.name = sle.voucher_no
                          AND se.purpose IN ('Material Receipt', 'Manufacture')
                    )
                )
              )
        """,
        {
            "item_code": item_code,
            "from_date": filters["from_date"],
            "to_date": filters["to_date"],
        },
        as_dict=True,
    )

    receipt_qty = receipt_res[0]["receipt_qty"] or 0

    # -------- TRUE CONSUMPTION --------
    consumption_res = frappe.db.sql(
        """
        SELECT ABS(SUM(sle.actual_qty)) AS consumption_qty
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabStock Entry` se
            ON se.name = sle.voucher_no
        WHERE sle.item_code = %(item_code)s
          AND sle.actual_qty < 0
          AND sle.voucher_type = 'Stock Entry'
          AND se.purpose IN ('Material Issue', 'Manufacture')
          AND sle.posting_date BETWEEN %(from_date)s AND %(to_date)s
        """,
        {
            "item_code": item_code,
            "from_date": filters["from_date"],
            "to_date": filters["to_date"],
        },
        as_dict=True,
    )

    consumption_qty = consumption_res[0]["consumption_qty"] or 0

    return receipt_qty, consumption_qty