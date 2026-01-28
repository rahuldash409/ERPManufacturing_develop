import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

@frappe.whitelist()
def after_install():
    create_custom_fields({
        "Manufacturing Settings":[
            dict(fieldname="section_break",label="Quality Inspection",fieldtype="Section Break",insert_after="validate_components_quantities_per_bom"),
            dict(fieldname="allow_multiple_qc",label="Allow multiple Quality Inspections for each Job Card",fieldtype="Check",insert_after="validate_components_quantities_per_bom"),
            dict(fieldname="default_raw_material_warehouse",label="Default Raw Material Warehouse",fieldtype="Link",options="Warehouse",insert_after="default_scrap_warehouse")
        ]
    })