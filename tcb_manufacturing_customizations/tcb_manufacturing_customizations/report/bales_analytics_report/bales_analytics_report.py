# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate


def execute(filters=None):
    """Main entry point for the report"""
    if not filters:
        filters = {}

    # Validate mandatory filters
    validate_filters(filters)

    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart_data(filters)
    report_summary = get_report_summary(filters)

    return columns, data, None, chart, report_summary


def validate_filters(filters):
    """Validate mandatory filters"""
    if not filters.get("from_date"):
        frappe.throw(_("From Date is required"))
    if not filters.get("to_date"):
        frappe.throw(_("To Date is required"))
    if getdate(filters.get("from_date")) > getdate(filters.get("to_date")):
        frappe.throw(_("From Date cannot be greater than To Date"))


def get_derived_source_case():
    """
    Returns SQL CASE statement for deriving source from source_document_type.
    - Bales Creator -> Manufacture
    - Purchase Receipt -> Import
    """
    return """
        CASE
            WHEN b.source_document_type = 'Bales Creator' THEN 'Manufacture'
            WHEN b.source_document_type = 'Purchase Receipt' THEN 'Import'
            ELSE 'Unknown'
        END
    """


def get_columns(filters):
    """Return columns based on source filter"""
    source = filters.get("source")

    columns = []

    if source == "Manufacture":
        # Parent-level columns for Manufacture source
        columns = [
            {
                "fieldname": "bales_creator_id",
                "label": _("Bales Creator ID"),
                "fieldtype": "Link",
                "options": "Bales Creator",
                "width": 160,
            },
            {
                "fieldname": "bale_id",
                "label": _("Bale ID"),
                "fieldtype": "Link",
                "options": "Bales",
                "width": 150,
            },
            {
                "fieldname": "item",
                "label": _("Item"),
                "fieldtype": "Link",
                "options": "Item",
                "width": 150,
            },
            {
                "fieldname": "batch",
                "label": _("Batch"),
                "fieldtype": "Link",
                "options": "Batch",
                "width": 120,
            },
            {
                "fieldname": "sub_batch",
                "label": _("Sub-batch"),
                "fieldtype": "Data",
                "width": 100,
            },
            {
                "fieldname": "quantity",
                "label": _("Quantity"),
                "fieldtype": "Float",
                "width": 100,
            },
            {
                "fieldname": "bales_status",
                "label": _("Status"),
                "fieldtype": "Data",
                "width": 120,
            },
            {
                "fieldname": "warehouse",
                "label": _("Warehouse"),
                "fieldtype": "Link",
                "options": "Warehouse",
                "width": 150,
            },
            {
                "fieldname": "creation_date",
                "label": _("Creation Date"),
                "fieldtype": "Date",
                "width": 110,
            },
            {
                "fieldname": "availability_date",
                "label": _("Availability Date"),
                "fieldtype": "Date",
                "width": 120,
            },
            {
                "fieldname": "dispatch_date",
                "label": _("Dispatch Date"),
                "fieldtype": "Date",
                "width": 110,
            },
            {
                "fieldname": "total_bales_count",
                "label": _("Total Bales"),
                "fieldtype": "Int",
                "width": 100,
            },
            {
                "fieldname": "status_summary",
                "label": _("Status Summary"),
                "fieldtype": "Data",
                "width": 200,
            },
            {
                "fieldname": "warehouse_summary",
                "label": _("Warehouse Summary"),
                "fieldtype": "Data",
                "width": 200,
            },
        ]
    else:
        # Columns for Import source (or all sources)
        columns = [
            {
                "fieldname": "bale_id",
                "label": _("Bale ID"),
                "fieldtype": "Link",
                "options": "Bales",
                "width": 150,
            },
            {
                "fieldname": "item",
                "label": _("Item"),
                "fieldtype": "Link",
                "options": "Item",
                "width": 150,
            },
            {
                "fieldname": "batch",
                "label": _("Batch"),
                "fieldtype": "Link",
                "options": "Batch",
                "width": 120,
            },
            {
                "fieldname": "sub_batch",
                "label": _("Sub-batch"),
                "fieldtype": "Data",
                "width": 100,
            },
            {
                "fieldname": "quantity",
                "label": _("Quantity"),
                "fieldtype": "Float",
                "width": 100,
            },
            {
                "fieldname": "bales_status",
                "label": _("Status"),
                "fieldtype": "Data",
                "width": 120,
            },
            {
                "fieldname": "warehouse",
                "label": _("Warehouse"),
                "fieldtype": "Link",
                "options": "Warehouse",
                "width": 150,
            },
            {
                "fieldname": "creation_date",
                "label": _("Creation Date"),
                "fieldtype": "Date",
                "width": 110,
            },
            {
                "fieldname": "availability_date",
                "label": _("Availability Date"),
                "fieldtype": "Date",
                "width": 120,
            },
            {
                "fieldname": "dispatch_date",
                "label": _("Dispatch Date"),
                "fieldtype": "Date",
                "width": 110,
            },
            {
                "fieldname": "source_document",
                "label": _("Source Document"),
                "fieldtype": "Dynamic Link",
                "options": "source_document_type",
                "width": 150,
            },
        ]

    return columns


def get_data(filters):
    """Get report data based on source filter"""
    source = filters.get("source")

    if source == "Manufacture":
        return get_manufacture_data(filters)
    elif source == "Import":
        return get_import_data(filters)
    else:
        # Return combined data for all sources
        return get_all_sources_data(filters)


def get_manufacture_data(filters):
    """
    Get data for Manufacture source with grouping by Bales Creator.
    Returns parent rows (Bales Creator) that can be expanded to show child rows (Bales).
    Source is derived from source_document_type = 'Bales Creator'.
    """
    data = []

    # Build conditions for Bales Creator
    bc_conditions = ["bc.docstatus = 1"]
    bc_values = {}

    if filters.get("from_date"):
        bc_conditions.append("bc.creation >= %(from_date)s")
        bc_values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        bc_conditions.append("bc.creation <= %(to_date)s")
        bc_values["to_date"] = filters.get("to_date")

    if filters.get("item"):
        bc_conditions.append("bc.item_code = %(item)s")
        bc_values["item"] = filters.get("item")

    if filters.get("warehouse"):
        bc_conditions.append("bc.warehouse = %(warehouse)s")
        bc_values["warehouse"] = filters.get("warehouse")

    bc_condition_str = " AND ".join(bc_conditions)

    # Get all Bales Creators with their items
    bales_creators = frappe.db.sql(
        f"""
        SELECT
            bc.name as bales_creator_id,
            bc.item_code,
            bc.item_name,
            bc.warehouse,
            bc.total_qty,
            bc.creation,
            bci.bales_id
        FROM `tabBales Creator` bc
        LEFT JOIN `tabBales Creator Item` bci ON bci.parent = bc.name
        WHERE {bc_condition_str}
        ORDER BY bc.creation DESC, bci.idx
    """,
        bc_values,
        as_dict=True,
    )

    # Group by Bales Creator
    creator_map = {}
    for row in bales_creators:
        creator_id = row.bales_creator_id
        if creator_id not in creator_map:
            creator_map[creator_id] = {"info": row, "bales_ids": []}
        if row.bales_id:
            creator_map[creator_id]["bales_ids"].append(row.bales_id)

    # Build Bales conditions
    bales_conditions = ["b.docstatus IN (0, 1)"]
    bales_values = {}

    if filters.get("bales_status"):
        bales_conditions.append("b.bales_status = %(bales_status)s")
        bales_values["bales_status"] = filters.get("bales_status")

    if filters.get("batch"):
        bales_conditions.append("bb.batch = %(batch)s")
        bales_values["batch"] = filters.get("batch")

    bales_condition_str = " AND ".join(bales_conditions)

    # Process each Bales Creator
    for creator_id, creator_data in creator_map.items():
        info = creator_data["info"]
        bales_ids = creator_data["bales_ids"]

        if not bales_ids:
            continue

        # Get all bales for this creator
        bales_ids_str = ", ".join([f"'{b}'" for b in bales_ids])
        bales_query = f"""
            SELECT
                b.name as bale_id,
                b.item,
                b.warehouse,
                b.bale_qty as quantity,
                b.bales_status,
                b.posting_date as creation_date,
                b.creation,
                b.delivery_note,
                bb.batch,
                bb.sub_batch
            FROM `tabBales` b
            LEFT JOIN `tabBales Batches` bb ON bb.parent = b.name
            WHERE b.name IN ({bales_ids_str})
            AND {bales_condition_str}
            ORDER BY b.creation DESC
        """

        bales_data = frappe.db.sql(bales_query, bales_values, as_dict=True)

        if not bales_data:
            continue

        # Calculate aggregates for parent row
        status_counts = {}
        warehouse_qty = {}
        total_qty = 0
        unique_bales = set()

        for bale in bales_data:
            if bale.bale_id not in unique_bales:
                unique_bales.add(bale.bale_id)
                status = bale.bales_status or "Unknown"
                status_counts[status] = status_counts.get(status, 0) + 1
                total_qty += flt(bale.quantity)

                wh = bale.warehouse or "Unknown"
                warehouse_qty[wh] = warehouse_qty.get(wh, 0) + flt(bale.quantity)

        # Format status summary
        status_summary = ", ".join([f"{k}: {v}" for k, v in status_counts.items()])
        warehouse_summary = ", ".join(
            [f"{k}: {flt(v, 2)}" for k, v in warehouse_qty.items()]
        )

        # Add parent row (Bales Creator level)
        parent_row = {
            "bales_creator_id": creator_id,
            "bale_id": "",
            "item": info.item_code,
            "batch": "",
            "sub_batch": "",
            "quantity": total_qty,
            "bales_status": "",
            "warehouse": info.warehouse,
            "creation_date": getdate(info.creation),
            "availability_date": None,
            "dispatch_date": None,
            "total_bales_count": len(unique_bales),
            "status_summary": status_summary,
            "warehouse_summary": warehouse_summary,
            "indent": 0,
            "is_group": 1,
        }
        data.append(parent_row)

        # Add child rows (individual Bales) - deduplicate by bale_id
        # Group batches by bale_id to avoid duplicate rows
        bales_by_id = {}
        for bale in bales_data:
            bale_id = bale.bale_id
            if bale_id not in bales_by_id:
                bales_by_id[bale_id] = {"bale": bale, "batches": [], "sub_batches": []}
            if bale.batch:
                bales_by_id[bale_id]["batches"].append(bale.batch)
            if bale.sub_batch:
                bales_by_id[bale_id]["sub_batches"].append(bale.sub_batch)

        for bale_id, bale_info in bales_by_id.items():
            bale = bale_info["bale"]
            # Get availability and dispatch dates
            availability_date = get_status_change_date(bale_id, "Packed Import")
            dispatch_date = get_status_change_date(bale_id, "Dispatched")

            # Combine batches and sub_batches into comma-separated strings
            batches_str = (
                ", ".join(set(bale_info["batches"])) if bale_info["batches"] else ""
            )
            sub_batches_str = (
                ", ".join(set(bale_info["sub_batches"]))
                if bale_info["sub_batches"]
                else ""
            )

            child_row = {
                "bales_creator_id": "",
                "bale_id": bale_id,
                "item": bale.item,
                "batch": batches_str,
                "sub_batch": sub_batches_str,
                "quantity": bale.quantity,
                "bales_status": bale.bales_status,
                "warehouse": bale.warehouse,
                "creation_date": bale.creation_date,
                "availability_date": availability_date,
                "dispatch_date": dispatch_date,
                "total_bales_count": None,
                "status_summary": "",
                "warehouse_summary": "",
                "indent": 1,
                "is_group": 0,
            }
            data.append(child_row)

    return data


def get_import_data(filters):
    """
    Get data for Import source - individual bale rows without grouping.
    Source is derived from source_document_type = 'Purchase Receipt'.
    """
    data = []

    # Build conditions - filter by source_document_type for Import
    conditions = [
        "b.docstatus IN (0, 1)",
        "b.source_document_type = 'Purchase Receipt'",
    ]
    values = {}

    if filters.get("from_date"):
        conditions.append("b.posting_date >= %(from_date)s")
        values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        conditions.append("b.posting_date <= %(to_date)s")
        values["to_date"] = filters.get("to_date")

    if filters.get("bales_status"):
        conditions.append("b.bales_status = %(bales_status)s")
        values["bales_status"] = filters.get("bales_status")

    if filters.get("item"):
        conditions.append("b.item = %(item)s")
        values["item"] = filters.get("item")

    if filters.get("warehouse"):
        conditions.append("b.warehouse = %(warehouse)s")
        values["warehouse"] = filters.get("warehouse")

    if filters.get("batch"):
        conditions.append("bb.batch = %(batch)s")
        values["batch"] = filters.get("batch")

    condition_str = " AND ".join(conditions)

    query = f"""
        SELECT DISTINCT
            b.name as bale_id,
            b.item,
            b.warehouse,
            b.bale_qty as quantity,
            b.bales_status,
            b.posting_date as creation_date,
            b.source_document_type,
            b.source_document,
            b.delivery_note,
            bb.batch,
            bb.sub_batch
        FROM `tabBales` b
        LEFT JOIN `tabBales Batches` bb ON bb.parent = b.name
        WHERE {condition_str}
        ORDER BY b.posting_date DESC, b.name
    """

    bales_data = frappe.db.sql(query, values, as_dict=True)

    # Deduplicate by bale_id - group batches together
    bales_by_id = {}
    for bale in bales_data:
        bale_id = bale.bale_id
        if bale_id not in bales_by_id:
            bales_by_id[bale_id] = {"bale": bale, "batches": [], "sub_batches": []}
        if bale.batch:
            bales_by_id[bale_id]["batches"].append(bale.batch)
        if bale.sub_batch:
            bales_by_id[bale_id]["sub_batches"].append(bale.sub_batch)

    for bale_id, bale_info in bales_by_id.items():
        bale = bale_info["bale"]
        availability_date = get_status_change_date(bale_id, "Packed Import")
        dispatch_date = get_status_change_date(bale_id, "Dispatched")

        # Combine batches into comma-separated strings
        batches_str = (
            ", ".join(set(bale_info["batches"])) if bale_info["batches"] else ""
        )
        sub_batches_str = (
            ", ".join(set(bale_info["sub_batches"])) if bale_info["sub_batches"] else ""
        )

        row = {
            "bale_id": bale_id,
            "item": bale.item,
            "batch": batches_str,
            "sub_batch": sub_batches_str,
            "quantity": bale.quantity,
            "bales_status": bale.bales_status,
            "warehouse": bale.warehouse,
            "creation_date": bale.creation_date,
            "availability_date": availability_date,
            "dispatch_date": dispatch_date,
            "source_document": bale.source_document,
            "source_document_type": bale.source_document_type,
        }
        data.append(row)

    return data


def get_all_sources_data(filters):
    """Get data for all sources combined"""
    data = []

    # Build conditions
    conditions = ["b.docstatus IN (0, 1)"]
    values = {}

    if filters.get("from_date"):
        conditions.append("b.posting_date >= %(from_date)s")
        values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        conditions.append("b.posting_date <= %(to_date)s")
        values["to_date"] = filters.get("to_date")

    if filters.get("bales_status"):
        conditions.append("b.bales_status = %(bales_status)s")
        values["bales_status"] = filters.get("bales_status")

    if filters.get("item"):
        conditions.append("b.item = %(item)s")
        values["item"] = filters.get("item")

    if filters.get("warehouse"):
        conditions.append("b.warehouse = %(warehouse)s")
        values["warehouse"] = filters.get("warehouse")

    if filters.get("batch"):
        conditions.append("bb.batch = %(batch)s")
        values["batch"] = filters.get("batch")

    condition_str = " AND ".join(conditions)

    query = f"""
        SELECT DISTINCT
            b.name as bale_id,
            b.item,
            b.warehouse,
            b.bale_qty as quantity,
            b.bales_status,
            b.posting_date as creation_date,
            b.source_document_type,
            b.source_document,
            b.delivery_note,
            bb.batch,
            bb.sub_batch
        FROM `tabBales` b
        LEFT JOIN `tabBales Batches` bb ON bb.parent = b.name
        WHERE {condition_str}
        ORDER BY b.posting_date DESC, b.name
    """

    bales_data = frappe.db.sql(query, values, as_dict=True)

    # Deduplicate by bale_id - group batches together
    # LEFT JOIN causes row multiplication when a Bale has multiple batches
    bales_by_id = {}
    for bale in bales_data:
        bale_id = bale.bale_id
        if bale_id not in bales_by_id:
            bales_by_id[bale_id] = {"bale": bale, "batches": [], "sub_batches": []}
        if bale.batch:
            bales_by_id[bale_id]["batches"].append(bale.batch)
        if bale.sub_batch:
            bales_by_id[bale_id]["sub_batches"].append(bale.sub_batch)

    for bale_id, bale_info in bales_by_id.items():
        bale = bale_info["bale"]
        availability_date = get_status_change_date(bale_id, "Packed Import")
        dispatch_date = get_status_change_date(bale_id, "Dispatched")

        # Combine batches into comma-separated strings
        batches_str = (
            ", ".join(set(bale_info["batches"])) if bale_info["batches"] else ""
        )
        sub_batches_str = (
            ", ".join(set(bale_info["sub_batches"])) if bale_info["sub_batches"] else ""
        )

        row = {
            "bale_id": bale_id,
            "item": bale.item,
            "batch": batches_str,
            "sub_batch": sub_batches_str,
            "quantity": bale.quantity,
            "bales_status": bale.bales_status,
            "warehouse": bale.warehouse,
            "creation_date": bale.creation_date,
            "availability_date": availability_date,
            "dispatch_date": dispatch_date,
            "source_document": bale.source_document,
            "source_document_type": bale.source_document_type,
        }
        data.append(row)

    return data


def get_status_change_date(bale_id, status):
    """
    Get the date when a bale transitioned to a specific status.
    Uses Version doctype to track status changes.
    """
    # Check current status first
    current_status = frappe.db.get_value("Bales", bale_id, "bales_status")

    if status == "Packed Import" and current_status in ["Packed Import", "Dispatched"]:
        # Try to get from version history
        versions = frappe.db.sql(
            """
            SELECT creation, data
            FROM `tabVersion`
            WHERE ref_doctype = 'Bales' AND docname = %s
            ORDER BY creation ASC
        """,
            (bale_id,),
            as_dict=True,
        )

        for version in versions:
            try:
                import json

                version_data = json.loads(version.data)
                for change in version_data.get("changed", []):
                    if change[0] == "bales_status" and change[2] == status:
                        return getdate(version.creation)
            except Exception:
                pass

        # Fallback: use posting_date
        if current_status in ["Packed Import", "Dispatched"]:
            return frappe.db.get_value("Bales", bale_id, "posting_date")

    elif status == "Dispatched" and current_status == "Dispatched":
        # Get from delivery note
        dn = frappe.db.get_value("Bales", bale_id, "delivery_note")
        if dn:
            return frappe.db.get_value("Delivery Note", dn, "posting_date")

    return None


def get_chart_data(filters):
    """Generate chart data based on filters"""
    # Get analytics data
    analytics = get_analytics_data(filters)

    # Primary chart: Status-wise bale count (Bar Chart)
    status_data = analytics.get("status_counts", {})

    chart = {
        "data": {
            "labels": list(status_data.keys()) if status_data else ["No Data"],
            "datasets": [
                {
                    "name": _("Bales Count"),
                    "values": list(status_data.values()) if status_data else [0],
                }
            ],
        },
        "type": "bar",
        "colors": ["#5e64ff"],
        "barOptions": {"stacked": False},
    }

    return chart


def get_report_summary(filters):
    """Generate report summary cards"""
    analytics = get_analytics_data(filters)

    summary = []

    # Total Bales
    summary.append(
        {
            "value": analytics.get("total_bales", 0),
            "label": _("Total Bales"),
            "datatype": "Int",
            "indicator": "blue",
        }
    )

    # Total Quantity
    summary.append(
        {
            "value": flt(analytics.get("total_quantity", 0), 2),
            "label": _("Total Quantity"),
            "datatype": "Float",
            "indicator": "blue",
        }
    )

    # Packed Import Bales
    summary.append(
        {
            "value": analytics.get("status_counts", {}).get("Packed Import", 0),
            "label": _("Packed Import Bales"),
            "datatype": "Int",
            "indicator": "green",
        }
    )

    # Dispatched Bales
    summary.append(
        {
            "value": analytics.get("status_counts", {}).get("Dispatched", 0),
            "label": _("Dispatched Bales"),
            "datatype": "Int",
            "indicator": "purple",
        }
    )

    # Pending Approval
    summary.append(
        {
            "value": analytics.get("status_counts", {}).get("Need Approval", 0),
            "label": _("Pending Approval"),
            "datatype": "Int",
            "indicator": "orange",
        }
    )

    # Manufacture vs Import percentages
    source_analytics = analytics.get("source_analytics", {})
    manufacture_pct = source_analytics.get("manufacture_pct", 0)
    import_pct = source_analytics.get("import_pct", 0)

    summary.append(
        {
            "value": f"{manufacture_pct}% / {import_pct}%",
            "label": _("Manufacture / Import"),
            "datatype": "Data",
            "indicator": "grey",
        }
    )

    # Average time to availability
    avg_time = analytics.get("avg_creation_to_availability", 0)
    summary.append(
        {
            "value": f"{flt(avg_time, 1)} days",
            "label": _("Avg. Time to Available"),
            "datatype": "Data",
            "indicator": "grey",
        }
    )

    return summary


def get_analytics_data(filters):
    """
    Calculate all analytics data based on filters.
    Source is derived from source_document_type field:
    - 'Bales Creator' -> Manufacture
    - 'Purchase Receipt' -> Import
    """
    analytics = {
        "total_bales": 0,
        "total_quantity": 0,
        "status_counts": {},
        "quantity_by_status": {},
        "quantity_by_item": {},
        "quantity_by_warehouse": {},
        "source_analytics": {},
        "flow_analytics": {},
        "time_analytics": {},
        "approval_analytics": {},
        "ledger_analytics": {},
    }

    # Build base conditions
    conditions = ["b.docstatus IN (0, 1)"]
    values = {}

    if filters.get("from_date"):
        conditions.append("b.posting_date >= %(from_date)s")
        values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        conditions.append("b.posting_date <= %(to_date)s")
        values["to_date"] = filters.get("to_date")

    # Source filter using derived logic
    if filters.get("source"):
        if filters.get("source") == "Manufacture":
            conditions.append("b.source_document_type = 'Bales Creator'")
        elif filters.get("source") == "Import":
            conditions.append("b.source_document_type = 'Purchase Receipt'")

    if filters.get("bales_status"):
        conditions.append("b.bales_status = %(bales_status)s")
        values["bales_status"] = filters.get("bales_status")

    if filters.get("item"):
        conditions.append("b.item = %(item)s")
        values["item"] = filters.get("item")

    if filters.get("warehouse"):
        conditions.append("b.warehouse = %(warehouse)s")
        values["warehouse"] = filters.get("warehouse")

    condition_str = " AND ".join(conditions)

    # 1. Status Analytics - Count of bales by status
    status_query = f"""
        SELECT
            b.bales_status,
            COUNT(DISTINCT b.name) as count,
            SUM(b.bale_qty) as total_qty
        FROM `tabBales` b
        WHERE {condition_str}
        GROUP BY b.bales_status
    """
    status_results = frappe.db.sql(status_query, values, as_dict=True)

    for row in status_results:
        status = row.bales_status or "Unknown"
        analytics["status_counts"][status] = row.count
        if status == "Packed In House":
            analytics["status_counts"]["Packed Import"] = (
                analytics["status_counts"].get("Packed Import", 0) + row.count
            )
        analytics["quantity_by_status"][status] = flt(row.total_qty)
        analytics["total_bales"] += row.count
        analytics["total_quantity"] += flt(row.total_qty)

    # 2. Quantity by Item
    item_query = f"""
        SELECT
            b.item,
            SUM(b.bale_qty) as total_qty
        FROM `tabBales` b
        WHERE {condition_str}
        GROUP BY b.item
        ORDER BY total_qty DESC
        LIMIT 10
    """
    item_results = frappe.db.sql(item_query, values, as_dict=True)
    for row in item_results:
        analytics["quantity_by_item"][row.item] = flt(row.total_qty)

    # 3. Quantity by Warehouse
    warehouse_query = f"""
        SELECT
            b.warehouse,
            SUM(b.bale_qty) as total_qty
        FROM `tabBales` b
        WHERE {condition_str}
        GROUP BY b.warehouse
        ORDER BY total_qty DESC
    """
    warehouse_results = frappe.db.sql(warehouse_query, values, as_dict=True)
    for row in warehouse_results:
        analytics["quantity_by_warehouse"][row.warehouse] = flt(row.total_qty)

    # 4. Source Analytics - Manufacture vs Import using derived source
    # Build base conditions without source filter for this calculation
    base_conditions = ["b.docstatus IN (0, 1)"]
    base_values = {}

    if filters.get("from_date"):
        base_conditions.append("b.posting_date >= %(from_date)s")
        base_values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        base_conditions.append("b.posting_date <= %(to_date)s")
        base_values["to_date"] = filters.get("to_date")

    if filters.get("bales_status"):
        base_conditions.append("b.bales_status = %(bales_status)s")
        base_values["bales_status"] = filters.get("bales_status")

    if filters.get("item"):
        base_conditions.append("b.item = %(item)s")
        base_values["item"] = filters.get("item")

    if filters.get("warehouse"):
        base_conditions.append("b.warehouse = %(warehouse)s")
        base_values["warehouse"] = filters.get("warehouse")

    base_condition_str = " AND ".join(base_conditions)

    # Use CASE-based derived source logic
    source_query = f"""
        SELECT
            CASE
                WHEN b.source_document_type = 'Bales Creator' THEN 'Manufacture'
                WHEN b.source_document_type = 'Purchase Receipt' THEN 'Import'
                ELSE 'Unknown'
            END as derived_source,
            COUNT(DISTINCT b.name) as count,
            SUM(b.bale_qty) as total_qty
        FROM `tabBales` b
        WHERE {base_condition_str}
        GROUP BY derived_source
    """
    source_results = frappe.db.sql(source_query, base_values, as_dict=True)

    manufacture_count = 0
    manufacture_qty = 0
    import_count = 0
    import_qty = 0

    for row in source_results:
        if row.derived_source == "Manufacture":
            manufacture_count = row.count or 0
            manufacture_qty = flt(row.total_qty)
        elif row.derived_source == "Import":
            import_count = row.count or 0
            import_qty = flt(row.total_qty)

    total_count = manufacture_count + import_count
    total_qty = manufacture_qty + import_qty

    analytics["source_analytics"] = {
        "manufacture_count": manufacture_count,
        "manufacture_qty": manufacture_qty,
        "manufacture_pct": round(
            (manufacture_count / total_count * 100) if total_count else 0, 1
        ),
        "import_count": import_count,
        "import_qty": import_qty,
        "import_pct": round(
            (import_count / total_count * 100) if total_count else 0, 1
        ),
    }

    # 5. Flow Analytics
    # Total created in period
    analytics["flow_analytics"]["created"] = analytics["total_bales"]

    # Total dispatched in period
    dispatched_conditions = conditions.copy()
    dispatched_conditions.append("b.bales_status = 'Dispatched'")
    dispatched_condition_str = " AND ".join(dispatched_conditions)

    dispatched_query = f"""
        SELECT COUNT(DISTINCT b.name) as count
        FROM `tabBales` b
        WHERE {dispatched_condition_str}
    """
    dispatched_result = frappe.db.sql(dispatched_query, values, as_dict=True)
    analytics["flow_analytics"]["dispatched"] = (
        dispatched_result[0].count if dispatched_result else 0
    )

    # Pending bales (not dispatched)
    pending_count = analytics["total_bales"] - analytics["flow_analytics"]["dispatched"]
    analytics["flow_analytics"]["pending"] = pending_count

    # 6. Time-based Analytics
    time_query = f"""
        SELECT
            b.name,
            b.posting_date as creation_date,
            b.bales_status
        FROM `tabBales` b
        WHERE {condition_str}
        AND b.bales_status IN ('Packed Import', 'Dispatched')
    """
    time_results = frappe.db.sql(time_query, values, as_dict=True)

    creation_to_availability_days = []
    availability_to_dispatch_days = []

    for bale in time_results:
        availability_date = get_status_change_date(bale.name, "Packed Import")
        if availability_date and bale.creation_date:
            days = date_diff(availability_date, bale.creation_date)
            if days >= 0:
                creation_to_availability_days.append(days)

        if bale.bales_status == "Dispatched":
            dispatch_date = get_status_change_date(bale.name, "Dispatched")
            if dispatch_date and availability_date:
                days = date_diff(dispatch_date, availability_date)
                if days >= 0:
                    availability_to_dispatch_days.append(days)

    analytics["avg_creation_to_availability"] = (
        sum(creation_to_availability_days) / len(creation_to_availability_days)
        if creation_to_availability_days
        else 0
    )
    analytics["avg_availability_to_dispatch"] = (
        sum(availability_to_dispatch_days) / len(availability_to_dispatch_days)
        if availability_to_dispatch_days
        else 0
    )

    # 7. Approval Analytics
    approval_conditions = conditions.copy()
    approval_conditions.append("b.bales_status = 'Need Approval'")
    approval_condition_str = " AND ".join(approval_conditions)

    approval_query = f"""
        SELECT COUNT(DISTINCT b.name) as count
        FROM `tabBales` b
        WHERE {approval_condition_str}
    """
    approval_result = frappe.db.sql(approval_query, values, as_dict=True)
    analytics["approval_analytics"]["pending_approval"] = (
        approval_result[0].count if approval_result else 0
    )

    # 8. Ledger Analytics
    ledger_conditions = ["1=1"]
    ledger_values = {}

    if filters.get("from_date"):
        ledger_conditions.append("ble.posting_date >= %(from_date)s")
        ledger_values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        ledger_conditions.append("ble.posting_date <= %(to_date)s")
        ledger_values["to_date"] = filters.get("to_date")

    ledger_condition_str = " AND ".join(ledger_conditions)

    ledger_query = f"""
        SELECT COUNT(*) as count
        FROM `tabBales Ledger Entry` ble
        WHERE {ledger_condition_str}
    """
    ledger_result = frappe.db.sql(ledger_query, ledger_values, as_dict=True)
    analytics["ledger_analytics"]["total_entries"] = (
        ledger_result[0].count if ledger_result else 0
    )

    return analytics


@frappe.whitelist()
def get_additional_charts(filters):
    """
    Get additional chart data for the report.
    Called via JavaScript to render multiple charts.
    """
    import json

    if isinstance(filters, str):
        filters = json.loads(filters)

    analytics = get_analytics_data(filters)
    charts = []

    # Chart 1: Status-wise bale count (Bar Chart)
    status_data = analytics.get("status_counts", {})
    charts.append(
        {
            "title": _("Bales by Status"),
            "data": {
                "labels": list(status_data.keys()) if status_data else ["No Data"],
                "datasets": [
                    {
                        "name": _("Count"),
                        "values": list(status_data.values()) if status_data else [0],
                    }
                ],
            },
            "type": "bar",
            "colors": ["#5e64ff"],
        }
    )

    # Chart 2: Manufacture vs Import (Pie Chart) - using derived source
    source_analytics = analytics.get("source_analytics", {})
    charts.append(
        {
            "title": _("Manufacture vs Import"),
            "data": {
                "labels": ["Manufacture", "Import"],
                "datasets": [
                    {
                        "name": _("Quantity"),
                        "values": [
                            source_analytics.get("manufacture_qty", 0),
                            source_analytics.get("import_qty", 0),
                        ],
                    }
                ],
            },
            "type": "pie",
            "colors": ["#7cd6fd", "#743ee2"],
        }
    )

    # Chart 3: Warehouse-wise quantity (Bar Chart)
    warehouse_data = analytics.get("quantity_by_warehouse", {})
    charts.append(
        {
            "title": _("Quantity by Warehouse"),
            "data": {
                "labels": (
                    list(warehouse_data.keys())[:10] if warehouse_data else ["No Data"]
                ),
                "datasets": [
                    {
                        "name": _("Quantity"),
                        "values": (
                            list(warehouse_data.values())[:10]
                            if warehouse_data
                            else [0]
                        ),
                    }
                ],
            },
            "type": "bar",
            "colors": ["#98d85b"],
        }
    )

    # Chart 4: Created vs Dispatched (Bar Chart)
    flow_analytics = analytics.get("flow_analytics", {})
    charts.append(
        {
            "title": _("Created vs Dispatched"),
            "data": {
                "labels": ["Created", "Dispatched", "Pending"],
                "datasets": [
                    {
                        "name": _("Bales"),
                        "values": [
                            flow_analytics.get("created", 0),
                            flow_analytics.get("dispatched", 0),
                            flow_analytics.get("pending", 0),
                        ],
                    }
                ],
            },
            "type": "bar",
            "colors": ["#5e64ff", "#28a745", "#ffc107"],
        }
    )

    return charts
