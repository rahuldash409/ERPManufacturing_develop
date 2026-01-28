import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_days, get_first_day, get_last_day


@frappe.whitelist()
def get_dashboard_data(from_date=None, to_date=None, company=None):
    """Get all dashboard data in a single call"""
    if not from_date:
        from_date = get_first_day(nowdate())
    if not to_date:
        to_date = get_last_day(nowdate())
    if not company:
        company = frappe.defaults.get_user_default("Company")

    filters = {
        "from_date": from_date,
        "to_date": to_date,
        "company": company,
    }

    return {
        "summary_cards": get_summary_cards(filters),
        "flow_funnel": get_flow_funnel_data(filters),
        "daily_trend": get_daily_trend(filters),
        "release_order_stats": get_release_order_stats(filters),
        "bales_stats": get_bales_stats(filters),
        "batch_consumption": get_batch_consumption_stats(filters),
        "top_customers": get_top_customers(filters),
        "pending_documents": get_pending_documents(filters),
    }


def get_summary_cards(filters):
    """Get summary card data for Quotation → SO → RO → DN flow"""
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    company = filters.get("company")

    # Quotations
    quotation_data = frappe.db.sql(
        """
        SELECT
            COUNT(*) as count,
            SUM(grand_total) as total_value,
            SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open_count,
            SUM(CASE WHEN status = 'Ordered' THEN 1 ELSE 0 END) as ordered_count
        FROM `tabQuotation`
        WHERE docstatus = 1
            AND transaction_date BETWEEN %s AND %s
            AND company = %s
    """,
        (from_date, to_date, company),
        as_dict=True,
    )[0]

    # Sales Orders
    so_data = frappe.db.sql(
        """
        SELECT
            COUNT(*) as count,
            SUM(grand_total) as total_value,
            SUM(total_qty) as total_qty,
            SUM(CASE WHEN status IN ('To Deliver', 'To Deliver and Bill') THEN 1 ELSE 0 END) as pending_delivery
        FROM `tabSales Order`
        WHERE docstatus = 1
            AND transaction_date BETWEEN %s AND %s
            AND company = %s
    """,
        (from_date, to_date, company),
        as_dict=True,
    )[0]

    # Release Orders
    ro_data = frappe.db.sql(
        """
        SELECT
            COUNT(*) as count,
            SUM(total_qty) as total_qty,
            SUM(CASE WHEN docstatus = 0 THEN 1 ELSE 0 END) as draft_count,
            SUM(CASE WHEN docstatus = 1 THEN 1 ELSE 0 END) as submitted_count
        FROM `tabRelease Order`
        WHERE posting_date BETWEEN %s AND %s
            AND company = %s
    """,
        (from_date, to_date, company),
        as_dict=True,
    )[0]

    # Delivery Notes
    dn_data = frappe.db.sql(
        """
        SELECT
            COUNT(*) as count,
            SUM(grand_total) as total_value,
            SUM(total_qty) as total_qty
        FROM `tabDelivery Note`
        WHERE docstatus = 1
            AND posting_date BETWEEN %s AND %s
            AND company = %s
    """,
        (from_date, to_date, company),
        as_dict=True,
    )[0]

    return {
        "quotation": {
            "count": quotation_data.get("count") or 0,
            "value": flt(quotation_data.get("total_value")),
            "open": quotation_data.get("open_count") or 0,
            "ordered": quotation_data.get("ordered_count") or 0,
        },
        "sales_order": {
            "count": so_data.get("count") or 0,
            "value": flt(so_data.get("total_value")),
            "qty": flt(so_data.get("total_qty")),
            "pending_delivery": so_data.get("pending_delivery") or 0,
        },
        "release_order": {
            "count": ro_data.get("count") or 0,
            "qty": flt(ro_data.get("total_qty")),
            "draft": ro_data.get("draft_count") or 0,
            "submitted": ro_data.get("submitted_count") or 0,
        },
        "delivery_note": {
            "count": dn_data.get("count") or 0,
            "value": flt(dn_data.get("total_value")),
            "qty": flt(dn_data.get("total_qty")),
        },
    }


def get_flow_funnel_data(filters):
    """Get funnel data showing conversion from Quotation to DN"""
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    company = filters.get("company")

    # Quotations created
    quotations = frappe.db.count(
        "Quotation",
        {
            "docstatus": 1,
            "transaction_date": ["between", [from_date, to_date]],
            "company": company,
        },
    )

    # Quotations converted to SO
    converted_quotations = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT q.name)
        FROM `tabQuotation` q
        INNER JOIN `tabSales Order Item` soi ON soi.prevdoc_docname = q.name
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE q.docstatus = 1
            AND so.docstatus = 1
            AND q.transaction_date BETWEEN %s AND %s
            AND q.company = %s
    """,
        (from_date, to_date, company),
    )[0][0] or 0

    # Sales Orders
    sales_orders = frappe.db.count(
        "Sales Order",
        {
            "docstatus": 1,
            "transaction_date": ["between", [from_date, to_date]],
            "company": company,
        },
    )

    # Release Orders
    release_orders = frappe.db.count(
        "Release Order",
        {
            "docstatus": 1,
            "posting_date": ["between", [from_date, to_date]],
            "company": company,
        },
    )

    # Delivery Notes
    delivery_notes = frappe.db.count(
        "Delivery Note",
        {
            "docstatus": 1,
            "posting_date": ["between", [from_date, to_date]],
            "company": company,
        },
    )

    return [
        {"stage": "Quotations", "count": quotations, "color": "#7C3AED"},
        {"stage": "Converted to SO", "count": converted_quotations, "color": "#8B5CF6"},
        {"stage": "Sales Orders", "count": sales_orders, "color": "#2563EB"},
        {"stage": "Release Orders", "count": release_orders, "color": "#0891B2"},
        {"stage": "Delivery Notes", "count": delivery_notes, "color": "#059669"},
    ]


def get_daily_trend(filters):
    """Get daily document creation trend"""
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    company = filters.get("company")

    # Get daily SO count
    so_trend = frappe.db.sql(
        """
        SELECT DATE(transaction_date) as date, COUNT(*) as count, SUM(total_qty) as qty
        FROM `tabSales Order`
        WHERE docstatus = 1
            AND transaction_date BETWEEN %s AND %s
            AND company = %s
        GROUP BY DATE(transaction_date)
        ORDER BY date
    """,
        (from_date, to_date, company),
        as_dict=True,
    )

    # Get daily DN count
    dn_trend = frappe.db.sql(
        """
        SELECT DATE(posting_date) as date, COUNT(*) as count, SUM(total_qty) as qty
        FROM `tabDelivery Note`
        WHERE docstatus = 1
            AND posting_date BETWEEN %s AND %s
            AND company = %s
        GROUP BY DATE(posting_date)
        ORDER BY date
    """,
        (from_date, to_date, company),
        as_dict=True,
    )

    # Get daily RO count
    ro_trend = frappe.db.sql(
        """
        SELECT DATE(posting_date) as date, COUNT(*) as count, SUM(total_qty) as qty
        FROM `tabRelease Order`
        WHERE docstatus = 1
            AND posting_date BETWEEN %s AND %s
            AND company = %s
        GROUP BY DATE(posting_date)
        ORDER BY date
    """,
        (from_date, to_date, company),
        as_dict=True,
    )

    return {
        "sales_orders": so_trend,
        "delivery_notes": dn_trend,
        "release_orders": ro_trend,
    }


def get_release_order_stats(filters):
    """Get Release Order specific statistics"""
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    company = filters.get("company")

    # Release Order by status
    status_data = frappe.db.sql(
        """
        SELECT
            CASE
                WHEN docstatus = 0 THEN 'Draft'
                WHEN docstatus = 1 THEN 'Submitted'
                WHEN docstatus = 2 THEN 'Cancelled'
            END as status,
            COUNT(*) as count,
            SUM(total_qty) as qty
        FROM `tabRelease Order`
        WHERE posting_date BETWEEN %s AND %s
            AND company = %s
        GROUP BY docstatus
    """,
        (from_date, to_date, company),
        as_dict=True,
    )

    # RO to DN conversion stats
    conversion_stats = frappe.db.sql(
        """
        SELECT
            COUNT(DISTINCT ro.name) as total_ro,
            COUNT(DISTINCT dn.name) as dn_created
        FROM `tabRelease Order` ro
        LEFT JOIN `tabDelivery Note` dn ON dn.custom_release_order = ro.name AND dn.docstatus = 1
        WHERE ro.docstatus = 1
            AND ro.posting_date BETWEEN %s AND %s
            AND ro.company = %s
    """,
        (from_date, to_date, company),
        as_dict=True,
    )[0]

    # Recent Release Orders
    recent_ros = frappe.db.sql(
        """
        SELECT
            ro.name,
            ro.sales_order,
            ro.customer_name,
            ro.total_qty,
            ro.posting_date,
            ro.docstatus
        FROM `tabRelease Order` ro
        WHERE ro.posting_date BETWEEN %s AND %s
            AND ro.company = %s
        ORDER BY ro.creation DESC
        LIMIT 5
    """,
        (from_date, to_date, company),
        as_dict=True,
    )

    return {
        "by_status": status_data,
        "conversion": conversion_stats,
        "recent": recent_ros,
    }


def get_bales_stats(filters):
    """Get Bales related statistics"""
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    # Bales by status
    status_data = frappe.db.sql(
        """
        SELECT
            bales_status as status,
            COUNT(*) as count,
            SUM(bale_qty) as qty
        FROM `tabBales`
        WHERE docstatus = 1
        GROUP BY bales_status
    """,
        as_dict=True,
    )

    # Bales dispatched in period
    dispatched = frappe.db.sql(
        """
        SELECT
            COUNT(*) as count,
            SUM(bale_qty) as qty
        FROM `tabBales`
        WHERE docstatus = 1
            AND bales_status = 'Dispatched'
            AND modified BETWEEN %s AND %s
    """,
        (from_date, to_date),
        as_dict=True,
    )[0]

    # Bales by source type
    by_source = frappe.db.sql(
        """
        SELECT
            source_document_type as source,
            COUNT(*) as count,
            SUM(bale_qty) as qty
        FROM `tabBales`
        WHERE docstatus = 1
        GROUP BY source_document_type
    """,
        as_dict=True,
    )

    # Recent bales linked to DNs
    recent_dn_bales = frappe.db.sql(
        """
        SELECT
            dnb.delivery_note,
            dnb.total_bales,
            dnb.total_qty,
            dn.customer_name,
            dn.posting_date
        FROM `tabDelivery Note Bales` dnb
        INNER JOIN `tabDelivery Note` dn ON dn.name = dnb.delivery_note
        WHERE dn.posting_date BETWEEN %s AND %s
        ORDER BY dnb.creation DESC
        LIMIT 5
    """,
        (from_date, to_date),
        as_dict=True,
    )

    return {
        "by_status": status_data,
        "dispatched_in_period": dispatched,
        "by_source": by_source,
        "recent_dn_bales": recent_dn_bales,
    }


def get_batch_consumption_stats(filters):
    """Get Serial and Batch Bundle consumption statistics"""
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    company = filters.get("company")

    # Bundles created for Delivery Notes
    bundle_stats = frappe.db.sql(
        """
        SELECT
            COUNT(*) as total_bundles,
            SUM(total_qty) as total_qty,
            COUNT(DISTINCT voucher_no) as unique_dns
        FROM `tabSerial and Batch Bundle`
        WHERE voucher_type = 'Delivery Note'
            AND type_of_transaction = 'Outward'
            AND docstatus = 1
            AND posting_date BETWEEN %s AND %s
            AND company = %s
    """,
        (from_date, to_date, company),
        as_dict=True,
    )[0]

    # Top items by batch consumption
    top_items = frappe.db.sql(
        """
        SELECT
            sbb.item_code,
            i.item_name,
            COUNT(*) as bundle_count,
            SUM(ABS(sbb.total_qty)) as total_consumed
        FROM `tabSerial and Batch Bundle` sbb
        INNER JOIN `tabItem` i ON i.name = sbb.item_code
        WHERE sbb.voucher_type = 'Delivery Note'
            AND sbb.type_of_transaction = 'Outward'
            AND sbb.docstatus = 1
            AND sbb.posting_date BETWEEN %s AND %s
            AND sbb.company = %s
        GROUP BY sbb.item_code
        ORDER BY total_consumed DESC
        LIMIT 5
    """,
        (from_date, to_date, company),
        as_dict=True,
    )

    # Daily batch consumption trend
    daily_consumption = frappe.db.sql(
        """
        SELECT
            DATE(posting_date) as date,
            COUNT(*) as bundles,
            SUM(ABS(total_qty)) as qty
        FROM `tabSerial and Batch Bundle`
        WHERE voucher_type = 'Delivery Note'
            AND type_of_transaction = 'Outward'
            AND docstatus = 1
            AND posting_date BETWEEN %s AND %s
            AND company = %s
        GROUP BY DATE(posting_date)
        ORDER BY date
    """,
        (from_date, to_date, company),
        as_dict=True,
    )

    return {
        "summary": bundle_stats,
        "top_items": top_items,
        "daily_trend": daily_consumption,
    }


def get_top_customers(filters):
    """Get top customers by sales value"""
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    company = filters.get("company")

    return frappe.db.sql(
        """
        SELECT
            customer,
            customer_name,
            COUNT(*) as order_count,
            SUM(grand_total) as total_value,
            SUM(total_qty) as total_qty
        FROM `tabSales Order`
        WHERE docstatus = 1
            AND transaction_date BETWEEN %s AND %s
            AND company = %s
        GROUP BY customer
        ORDER BY total_value DESC
        LIMIT 5
    """,
        (from_date, to_date, company),
        as_dict=True,
    )


def get_pending_documents(filters):
    """Get pending documents requiring action"""
    company = filters.get("company")

    # Pending Quotations (Open)
    pending_quotations = frappe.db.sql(
        """
        SELECT name, customer_name, grand_total, transaction_date
        FROM `tabQuotation`
        WHERE docstatus = 1
            AND status = 'Open'
            AND company = %s
        ORDER BY transaction_date DESC
        LIMIT 5
    """,
        (company,),
        as_dict=True,
    )

    # Pending SO (To Deliver)
    pending_so = frappe.db.sql(
        """
        SELECT name, customer_name, grand_total, total_qty, transaction_date
        FROM `tabSales Order`
        WHERE docstatus = 1
            AND status IN ('To Deliver', 'To Deliver and Bill')
            AND company = %s
        ORDER BY transaction_date ASC
        LIMIT 5
    """,
        (company,),
        as_dict=True,
    )

    # Draft Release Orders
    draft_ro = frappe.db.sql(
        """
        SELECT name, sales_order, customer_name, total_qty, posting_date
        FROM `tabRelease Order`
        WHERE docstatus = 0
            AND company = %s
        ORDER BY creation DESC
        LIMIT 5
    """,
        (company,),
        as_dict=True,
    )

    # Draft Delivery Notes
    draft_dn = frappe.db.sql(
        """
        SELECT name, customer_name, grand_total, total_qty, posting_date
        FROM `tabDelivery Note`
        WHERE docstatus = 0
            AND company = %s
        ORDER BY creation DESC
        LIMIT 5
    """,
        (company,),
        as_dict=True,
    )

    return {
        "quotations": pending_quotations,
        "sales_orders": pending_so,
        "release_orders": draft_ro,
        "delivery_notes": draft_dn,
    }
