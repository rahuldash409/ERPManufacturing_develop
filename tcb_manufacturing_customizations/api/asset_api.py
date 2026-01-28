import frappe
from frappe import _

@frappe.whitelist()
def get_warehouses_for_stock_entry(asset_name, stock_entry_type):
    """
    Get warehouse details for creating stock entry from asset
    Returns source and target warehouse based on stock entry type
    """
    
    workstation = frappe.db.get_value(
        'Workstation',
        {'custom_asset': asset_name},
        ['name', 'warehouse'],
        as_dict=1
    )
    
    if not workstation:
        frappe.throw(_("No workstation found linked to this asset"))
    
    settings = frappe.get_single("Workstation Spares Settings")
    
    if not settings:
        frappe.throw(_("Workstation Spares Settings not configured"))
    
    source_warehouse = None
    target_warehouse = None
    
    if stock_entry_type == "Spares Transfer":
        source_warehouse = settings.default_racks_warehouse
        target_warehouse = workstation.warehouse
        
    elif stock_entry_type == "Spares Consumption":
        source_warehouse = workstation.warehouse
        target_warehouse = None
        
    elif stock_entry_type == "Material Transfer":
        source_warehouse = workstation.warehouse
        target_warehouse = settings.default_racks_warehouse
    
    return {
        "workstation": workstation.name,
        "source_warehouse": source_warehouse,
        "target_warehouse": target_warehouse,
        "stock_entry_type": stock_entry_type
    }


@frappe.whitelist()
def get_linked_purchase_orders(asset_name):
    """
    Get all Purchase Orders linked to this Asset via Service Requests
    Asset reference is in Service Request Detail (child table)
    """
    
    # Step 1: Get Service Request names where asset is in child table
    service_requests = frappe.db.sql("""
        SELECT DISTINCT parent
        FROM `tabService Request Detail`
        WHERE asset_reference = %s
        AND parenttype = 'Service Request'
    """, (asset_name,), as_dict=0)
    
        # AND docstatus != 2
    if not service_requests:
        return []
    
    # Extract SR names from tuple result
    sr_names = [sr[0] for sr in service_requests]
    
    # Step 2: Get Purchase Orders linked to these Service Requests
    purchase_orders = frappe.get_all(
        'Purchase Order',
        filters={
            'custom_po_reference': ['in', sr_names],
            'docstatus': ['!=', 2]
        },
        fields=[
            'name as po_name',
            'custom_po_reference as sr_name',
            'transaction_date',
            'supplier',
            'docstatus',
            'status'
        ],
        order_by='transaction_date desc'
    )
    
    return purchase_orders
