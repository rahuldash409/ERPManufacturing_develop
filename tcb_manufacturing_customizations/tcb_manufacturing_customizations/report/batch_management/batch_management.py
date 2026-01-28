import frappe
from frappe.utils import flt

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"fieldname": "item", "label": "Item", "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "item_name", "label": "Item Name", "fieldtype": "Data", "width": 220},
        {"fieldname": "item_group", "label": "Item Group", "fieldtype": "Link", "options": "Item Group", "width": 150},
        {"fieldname": "warehouse", "label": "Warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"fieldname": "batch_no", "label": "Batch", "fieldtype": "Link", "options": "Batch", "width": 150},
        {"fieldname": "sub_batch", "label": "Sub Batch", "fieldtype": "Data", "width": 150},
        {"fieldname": "container_name", "label": "Container Name", "fieldtype": "Data", "width": 150},
        {"fieldname": "container_number", "label": "Container Number", "fieldtype": "Data", "width": 150},
        {"fieldname": "batch_date", "label": "Batch Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "qty", "label": "Available Qty", "fieldtype": "Float", "width": 150}
    ]

def get_data(filters):
    conditions = ""
    filter_values = {}
    
    if filters:
        if filters.get("item"):
            conditions += " AND sle.item_code = %(item)s"
            filter_values["item"] = filters.get("item")
        if filters.get("warehouse"):
            conditions += " AND sle.warehouse = %(warehouse)s"
            filter_values["warehouse"] = filters.get("warehouse")
        if filters.get("item_group"):
            conditions += " AND i.item_group = %(item_group)s"
            filter_values["item_group"] = filters.get("item_group")
    
    # Get stock ledger entries with serial and batch bundles
    query = """
        SELECT 
            sle.item_code,
            sle.warehouse,
            sle.serial_and_batch_bundle,
            SUM(sle.actual_qty) as qty
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` i ON sle.item_code = i.name
        WHERE 
            sle.serial_and_batch_bundle IS NOT NULL
            AND sle.serial_and_batch_bundle != ''
            AND sle.is_cancelled = 0
            {conditions}
        GROUP BY 
            sle.item_code, sle.warehouse, sle.serial_and_batch_bundle
        HAVING 
            SUM(sle.actual_qty) > 0
    """.format(conditions=conditions)
    
    sle_data = frappe.db.sql(query, filter_values, as_dict=1)
    
    data = []
    processed_combinations = set()
    
    for sle in sle_data:
        if not sle.serial_and_batch_bundle:
            continue
            
        # Get batch entries from the bundle with batch creation date for FIFO
        bundle_entries = frappe.db.sql("""
            SELECT 
                sbbe.batch_no,
                sbbe.warehouse,
                sbbe.qty,
                b.creation as batch_date
            FROM `tabSerial and Batch Entry` sbbe
            INNER JOIN `tabBatch` b ON sbbe.batch_no = b.name
            WHERE sbbe.parent = %s
                AND sbbe.batch_no IS NOT NULL
                AND sbbe.batch_no != ''
        """, sle.serial_and_batch_bundle, as_dict=1)
        
        for entry in bundle_entries:
            # Create unique key to avoid duplicates
            key = (sle.item_code, entry.warehouse, entry.batch_no)
            
            if key in processed_combinations:
                continue
            
            # Get actual available qty for this batch in this warehouse
            batch_qty = get_batch_qty(entry.batch_no, entry.warehouse)
            
            if batch_qty <= 0:
                continue
            
            # Get batch details
            batch_details = frappe.db.get_value("Batch", entry.batch_no, 
                ["item", "item_name", "custom_sub_batch", "custom_container_name", "custom_container_number"],
                as_dict=1)
            
            if not batch_details:
                continue
            
            # Get item group
            item_group = frappe.db.get_value("Item", batch_details.item, "item_group")
            
            data.append({
                "item": batch_details.item,
                "item_name": batch_details.item_name,
                "item_group": item_group,
                "warehouse": entry.warehouse,
                "batch_no": entry.batch_no,
                "sub_batch": batch_details.custom_sub_batch,
                "container_name": batch_details.custom_container_name,
                "container_number": batch_details.custom_container_number,
                "batch_date": entry.batch_date,
                "qty": flt(batch_qty, 2)
            })
            
            processed_combinations.add(key)
    
    # Sort data by FIFO (oldest batches first)
    data = sorted(data, key=lambda x: (x["item"], x["warehouse"], x["batch_date"], x["batch_no"]))
    
    return data

def get_batch_qty(batch_no, warehouse):
    """Get available quantity for a batch in a specific warehouse"""
    result = frappe.db.sql("""
        SELECT SUM(sbbe.qty) as qty
        FROM `tabSerial and Batch Entry` sbbe
        INNER JOIN `tabSerial and Batch Bundle` sbb ON sbbe.parent = sbb.name
        INNER JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sbb.name
        WHERE 
            sbbe.batch_no = %s
            AND sbbe.warehouse = %s
            AND sle.is_cancelled = 0
            AND sle.docstatus = 1
    """, (batch_no, warehouse), as_dict=1)
    
    return flt(result[0].qty) if result and result[0].qty else 0