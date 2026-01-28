# File: tcb_manufacturing_customizations/api/asset_maintenance_api.py

import frappe
from frappe import _

@frappe.whitelist()
def get_asset_from_maintenance(asset_maintenance_name):
    """
    Get Asset name from Asset Maintenance
    """
    if not asset_maintenance_name:
        return None
    
    asset_name = frappe.db.get_value(
        "Asset Maintenance",
        asset_maintenance_name,
        "asset_name"
    )
    
    return asset_name


@frappe.whitelist()
def get_workstation_and_warehouse_for_maintenance(asset_name):
    """
    Get workstation and warehouse details for Asset Maintenance Log
    Similar to Asset Repair logic
    """
    
    if not asset_name:
        frappe.throw(_("Asset is required"))
    
    # Get Workstation linked to Asset
    workstation = frappe.db.get_value(
        "Workstation",
        {"custom_asset": asset_name},
        ["name", "warehouse"],
        as_dict=1
    )
    
    if not workstation:
        frappe.throw(
            _("No Workstation found linked with Asset {0}").format(asset_name),
            title=_("Workstation Not Found")
        )
    
    if not workstation.warehouse:
        frappe.throw(
            _("Warehouse not configured for Workstation {0}").format(workstation.name),
            title=_("Warehouse Missing")
        )
    
    # Get Spares Transfer Source Warehouse from Settings
    spares_settings = frappe.get_cached_doc(
        "Workstation Spares Settings",
        "Workstation Spares Settings"
    )
    
    if not spares_settings.default_spares_transfer_source_warehouse:
        frappe.throw(
            _("Spares Transfer Source Warehouse not configured in Workstation Spares Settings"),
            title=_("Settings Incomplete")
        )
    
    return {
        "workstation": workstation.name,
        "target_warehouse": workstation.warehouse,
        "source_warehouse": spares_settings.default_spares_transfer_source_warehouse
    }

@frappe.whitelist()
def update_spares_status_for_maintenance(maintenance_log_name):
    """
    Update spares transfer/consume/return flags based on Stock Entries
    UPDATED: Uses custom_another_stock_entry_reference field
    """
    
    if not maintenance_log_name:
        return
    
    # Count Stock Entries by type
    stock_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "custom_another_stock_entry_reference": maintenance_log_name,
            "docstatus": 1
        },
        fields=["stock_entry_type"]
    )
    
    transfer_count = sum(1 for se in stock_entries if se.stock_entry_type == "Spares Transfer")
    consumption_count = sum(1 for se in stock_entries if se.stock_entry_type == "Spares Consumption")
    return_count = sum(1 for se in stock_entries if se.stock_entry_type == "Material Transfer")
    
    # Update flags in Maintenance Log
    frappe.db.set_value(
        "Asset Maintenance Log",
        maintenance_log_name,
        {
            "custom_spares_transferred": 1 if transfer_count > 0 else 0,
            "custom_spares_consumed": 1 if consumption_count > 0 else 0,
            "custom_spares_returned": 1 if return_count > 0 else 0
        }
    )
    
    frappe.db.commit()
    
    return {
        "transferred": transfer_count,
        "consumed": consumption_count,
        "returned": return_count
    }


@frappe.whitelist()
def check_draft_stock_entries_for_maintenance(maintenance_log_name):
    """
    Check if any draft Stock Entries exist for this Maintenance Log
    UPDATED: Uses custom_another_stock_entry_reference field
    """
    
    draft_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "custom_another_stock_entry_reference": maintenance_log_name,
            "docstatus": 0
        },
        fields=["name", "stock_entry_type"],
        limit=5
    )
    
    return draft_entries
