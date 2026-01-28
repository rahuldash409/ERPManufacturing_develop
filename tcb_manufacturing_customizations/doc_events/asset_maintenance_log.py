
import frappe
from frappe import _
from frappe.model.document import Document


def validate(self):
    """Validate and auto-fetch asset details"""
    if self.asset_maintenance and not self.custom_asset:
        self.custom_asset = frappe.db.get_value(
            "Asset Maintenance",
            self.asset_maintenance,
            "asset_name"
        )
    
    # Fetch workstation if asset exists
    if self.custom_asset and not self.custom_workstation:
        self.fetch_workstation_details()

def fetch_workstation_details(self):
    """Fetch workstation and warehouse from asset"""
    workstation = frappe.db.get_value(
        "Workstation",
        {"custom_asset": self.custom_asset},
        ["name", "warehouse"],
        as_dict=1
    )
    
    if workstation:
        self.custom_workstation = workstation.name
        self.custom_warehouse = workstation.warehouse

def on_submit(self):
    """Update spares status after submit"""
    self.update_spares_flags()

def on_cancel(self):
    """Check for linked stock entries before cancel"""
    linked_stock_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "custom_another_stock_entry_reference": self.name,
            "docstatus": 1
        },
        limit=1
    )
    
    if linked_stock_entries:
        frappe.throw(
            _("Cannot cancel this Maintenance Log. It has submitted Stock Entries linked to it."),
            title=_("Linked Documents Exist")
        )

def update_spares_flags(self):
    """Update spares transfer/consume/return checkboxes"""
    stock_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "custom_another_stock_entry_reference": self.name,
            "docstatus": 1
        },
        fields=["stock_entry_type"]
    )
    
    self.custom_spares_transferred = any(
        se.stock_entry_type == "Spares Transfer" for se in stock_entries
    )
    self.custom_spares_consumed = any(
        se.stock_entry_type == "Spares Consumption" for se in stock_entries
    )
    self.custom_spares_returned = any(
        se.stock_entry_type == "Material Transfer" for se in stock_entries
    )