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


# --------------------------------
# Columns
# --------------------------------
def get_columns():
    return [
        {
            "label": "Item",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 240,
        },
        {
            "label": "Item Group",
            "fieldname": "item_group",
            "fieldtype": "Data",
            "width": 200,
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
            "width": 140,
        },
        {
            "label": "Closing Qty",
            "fieldname": "closing_qty",
            "fieldtype": "Float",
            "width": 120,
        },
    ]


# --------------------------------
# Data Builder (ITEM WISE + GROUPED)
# --------------------------------
def get_data(filters):
    data = []

    items = get_items()

    # fixed group order
    group_order_map = {g: i for i, g in enumerate(ALLOWED_ITEM_GROUPS)}

    # sort items by group order then item name
    items = sorted(
        items,
        key=lambda x: (
            group_order_map.get(x.item_group, 999),
            x.name
        )
    )

    current_group = None

    # group subtotal holders
    g_open = g_receipt = g_consume = g_close = 0

    for item in items:
        item_code = item.name
        item_group = item.item_group

        # ---- New Group ----
        if current_group != item_group:
            if current_group is not None:
                # subtotal row
                data.append({
                    "item_code": f"{current_group.upper()} TOTAL",
                    "opening_qty": g_open,
                    "receipt_qty": g_receipt,
                    "consumption_qty": g_consume,
                    "closing_qty": g_close,
                })
                # blank row
                data.append({})

            # group heading
            data.append({
                "item_code": item_group.upper(),
                "opening_qty": None,
                "receipt_qty": None,
                "consumption_qty": None,
                "closing_qty": None,
            })

            g_open = g_receipt = g_consume = g_close = 0
            current_group = item_group

        # item calculations
        opening = get_opening_qty(item_code, filters)
        receipt, consumption = get_movement_qty(item_code, filters)
        closing = get_closing_qty(item_code, filters)

        # skip fully zero rows
        if opening == receipt == consumption == closing == 0:
            continue

        # item row
        data.append({
            "item_code": f"  {item_code}",
            "item_group": item_group,
            "opening_qty": opening,
            "receipt_qty": receipt,
            "consumption_qty": consumption,
            "closing_qty": closing,
        })

        # accumulate subtotals
        g_open += opening
        g_receipt += receipt
        g_consume += consumption
        g_close += closing

    # last group subtotal
    if current_group:
        data.append({
            "item_code": f"{current_group.upper()} TOTAL",
            "opening_qty": g_open,
            "receipt_qty": g_receipt,
            "consumption_qty": g_consume,
            "closing_qty": g_close,
        })

    return data


# --------------------------------
# Get Items (restricted groups)
# --------------------------------
def get_items():
    return frappe.get_all(
        "Item",
        filters={
            "item_group": ["in", ALLOWED_ITEM_GROUPS],
            "disabled": 0,
        },
        fields=["name", "item_group"],
    )


# --------------------------------
# Opening Stock (ALL WAREHOUSES)
# --------------------------------
def get_opening_qty(item_code, filters):
    result = frappe.db.sql(
        """
        SELECT SUM(qty_after_transaction) AS opening_qty
        FROM (
            SELECT sle.warehouse, sle.qty_after_transaction
            FROM `tabStock Ledger Entry` sle
            INNER JOIN (
                SELECT warehouse,
                       MAX(CONCAT(posting_date, ' ', posting_time, ' ', creation)) AS max_dt
                FROM `tabStock Ledger Entry`
                WHERE item_code = %(item_code)s
                  AND posting_date < %(from_date)s
                GROUP BY warehouse
            ) last_sle
            ON last_sle.warehouse = sle.warehouse
           AND CONCAT(sle.posting_date, ' ', sle.posting_time, ' ', sle.creation) = last_sle.max_dt
        ) t
        """,
        {
            "item_code": item_code,
            "from_date": filters["from_date"],
        },
        as_dict=True,
    )

    return result[0]["opening_qty"] or 0


# --------------------------------
# Receipt & TRUE Consumption
# --------------------------------
def get_movement_qty(item_code, filters):

    # ---- Receipt (all incoming, all warehouses) ----
    receipt_res = frappe.db.sql(
        """
        SELECT SUM(actual_qty) AS receipt_qty
        FROM `tabStock Ledger Entry`
        WHERE item_code = %(item_code)s
          AND actual_qty > 0
          AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        """,
        {
            "item_code": item_code,
            "from_date": filters["from_date"],
            "to_date": filters["to_date"],
        },
        as_dict=True,
    )

    receipt_qty = receipt_res[0]["receipt_qty"] or 0

    # ---- TRUE CONSUMPTION (exclude transfers) ----
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


# --------------------------------
# Closing Stock (ALL WAREHOUSES)
# --------------------------------
def get_closing_qty(item_code, filters):
    result = frappe.db.sql(
        """
        SELECT SUM(qty_after_transaction) AS closing_qty
        FROM (
            SELECT sle.warehouse, sle.qty_after_transaction
            FROM `tabStock Ledger Entry` sle
            INNER JOIN (
                SELECT warehouse,
                       MAX(CONCAT(posting_date, ' ', posting_time, ' ', creation)) AS max_dt
                FROM `tabStock Ledger Entry`
                WHERE item_code = %(item_code)s
                  AND posting_date <= %(to_date)s
                GROUP BY warehouse
            ) last_sle
            ON last_sle.warehouse = sle.warehouse
           AND CONCAT(sle.posting_date, ' ', sle.posting_time, ' ', sle.creation) = last_sle.max_dt
        ) t
        """,
        {
            "item_code": item_code,
            "to_date": filters["to_date"],
        },
        as_dict=True,
    )

    return result[0]["closing_qty"] or 0