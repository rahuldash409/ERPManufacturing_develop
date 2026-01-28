# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import days_diff

class WorkstationSpareParts(Document):
    
    def validate(self):
        pass
        # if self.date_of_installation and self.dispose_replacement_date :
        #     if self.date_of_installation > self.dispose_replacement_date:
        #         frappe.throw("Invalid Date Selection: The Dispose/Replacement Date must be after the Date of Installation.")
        #     else:
        #         part_life_days = days_diff(self.dispose_replacement_date ,self.date_of_installation)
        #         # #print("--------------------",part_life_days)
        #         self.service_life_days = part_life_days
				


    # @frappe.whitelist()
    # def create_stock_entry(self):
    #     """Create Material Transfer Stock Entry - Called from button"""
        
    #     # Get Item UOM
    #     item_uom = frappe.db.get_value('Item', self.spare_part, 'stock_uom')
        
    #     if not item_uom:
    #         frappe.throw(('Could not fetch UOM for Item {0}').format(self.spare_part))
        
    #     # Create Stock Entry
    #     stock_entry = frappe.get_doc({
    #         'doctype': 'Stock Entry',
    #         'stock_entry_type': 'Material Transfer',
    #         'to_warehouse': self.workstation_warehouse,
    #         'set_posting_time': 1,
    #         'posting_date': self.date_of_installation,
    #         'from_warehouse': self.workstation_warehouse,
            
    #         'items': [{
    #             'item_code': self.spare_part,
    #             'qty': 1,
    #             'uom': item_uom,
    #             'stock_uom': item_uom,
    #             'conversion_factor': 1,
    #             # 'to_warehouse': self.workstation_warehouse,
    #             # 'source_warehouse': self.workstation_warehouse
                
    #         }]
    #     })
        
    #     stock_entry.insert()
    #     # frappe.db.commit()
        
    #     frappe.msg#print(('Stock Entry {0} created successfully').format(
    #         '<a href="/app/stock-entry/{0}">{0}</a>'.format(stock_entry.name)
    #     ), indicator='green')
        
    #     return stock_entry.name
    
@frappe.whitelist()
def create_move_history(data):
    # #print('=================here is the row data-=========', data)
    data = frappe.parse_json(data)
    doc = frappe.new_doc("Spares Move History")
    doc.update(data)
    # #print('===================here is the new spare move history doc ======================== ', doc)
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def update_spare_status(docname,new_status):
    doc = frappe.get_doc("Workstation Spare Parts", docname)
    doc.spare_status = new_status
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return "OK"


# file: tcb_manufacturing_customizations/api.py
@frappe.whitelist()
def create_service_request_for_supplier(data=None):
    # Check if "Repair Service" item exists, if not create it
    repair_service_item = "Repair Service"
    
    # if not frappe.db.exists("Item", repair_service_item):
    #     # Create the item if it doesn't exist
    #     repair_item_doc = frappe.get_doc({
    #         "doctype": "Item",
    #         "item_code": repair_service_item,
    #         "item_name": repair_service_item,
    #         "item_group": "Services",
    #         "is_stock_item": 0,
    #         "maintain_stock": 0
    #     })
    #     repair_item_doc.insert(ignore_permissions=True)
    #     frappe.db.commit()
    if isinstance(data, str):
        import json
        data = json.loads(data)

    supplier = data.get("supplier")
    asset_repair_reference = data.get("asset_repair_reference")
    #print('=================here is the data to asset repriar reference  =========', asset_repair_reference)
    schedule_date = data.get("schedule_date")
    rows = data.get("rows") or []

    line_ids = [r.get("line_id") for r in rows]
    spare_items = [r.get("spare_part") for r in rows if r.get("spare_part")]
    spare_items_unique = list(dict.fromkeys(spare_items))

    description_lines = [
        _("Service Request created for repair service for the following workstation spare lines:"),
        _("Line IDs / Serial Nos: {0}\n").format(", ".join(line_ids)),
        _("Spare Items: {0}\n").format(", ".join(spare_items_unique)),
        _("Details: This SR aggregates repair requests generated on {0}.\n").format(frappe.utils.getdate()),
        _("Rows included:"),
    ]
    for r in rows:
        description_lines.append(
            f"- Line: {r.get('line_id')},\nItem: {r.get('spare_part')}, \nSerial: {r.get('serial_no')}, \nFrom: {r.get('source_warehouse')} -> To: {r.get('target_warehouse')}"
        )

    full_description = "\n\n".join(description_lines)

    try:
        # Group items by spare_part to avoid duplicates
        items_dict = {}
        
        for r in rows:
            spare_part = r.get("spare_part")
            asset_reference = r.get("asset") or "N/A"
            line_id = r.get("line_id") or "N/A"
            serial_no = r.get("serial_no") or "N/A"
            source_wh = r.get("source_warehouse") or "N/A"
            target_wh = r.get("target_warehouse") or "N/A"
            
            # If item already exists, increment qty and append details
            if spare_part in items_dict:
                items_dict[spare_part]["qty"] += 1
                items_dict[spare_part]["serial_nos"].append(serial_no)
                items_dict[spare_part]["line_id"].append(line_id)
                
                items_dict[spare_part]["details"].append({
                    "line_id": line_id,
                    "serial_no": serial_no,
                    "source_wh": source_wh,
                    "target_wh": target_wh
                })
            else:
                # Create new entry
                items_dict[spare_part] = {
                    "qty": 1,
                    "serial_nos": [serial_no],
                    "line_id": [line_id],
                    "source_wh": source_wh,
                    "target_wh": target_wh,
                    "details": [{
                        "line_id": line_id,
                        "serial_no": serial_no,
                        "source_wh": source_wh,
                        "target_wh": target_wh
                    }]
                }
        
        # Build PO items list from grouped data
        sr_items = []
        for spare_part, item_data in items_dict.items():
            qty = item_data["qty"]
            details = item_data["details"]
            serial_nos = item_data["serial_nos"]
            line_ids = item_data["line_id"]
            source_wh = item_data["source_wh"]
            target_wh = item_data["target_wh"]
            
            # Build description with all details for this item
            desc_lines = [
                f"Repair service for spare item: {spare_part}",
                f"Total Quantity: {qty}\n",
                "Details:"
            ]
            
            for idx, detail in enumerate(details, 1):
                desc_lines.append(
                    f"{idx}. Line ID: {detail['line_id']}, "
                    f"Serial: {detail['serial_no']}, "
                    f"From: {detail['source_wh']} → To: {detail['target_wh']}"
                )
            
            item_description = "\n".join(desc_lines)
            serial_nos_text = "\n".join(serial_nos)
            line_ids_text = "\n".join(line_ids)
            sr_items.append({
                "item": repair_service_item,
                "qty": qty,
                "description": item_description,
                "serial_no": serial_nos_text, 
                "linked_item": spare_part,
                "asset_reference": asset_reference,
                "workstation_spare_doc_names": line_ids_text,
                "from_warehouse": source_wh,
                "to_warehouse": target_wh,
            })

        sr_doc = frappe.get_doc({
            "doctype": "Service Request",
            "supplier": supplier,
            "date": schedule_date,
            # "schedule_date": schedule_date,
            "service_request_item_details": sr_items,
            "remarks": full_description,
            "asset_repair_reference": asset_repair_reference,
            # 'spares_move_reference': ", ".join(line_ids),
        })

        sr_doc.insert(ignore_permissions=True)
        return {"sr_name": sr_doc.name}

    except Exception as e:
        frappe.log_error("Service Request Creation Error", frappe.get_traceback())

        if "Repair Service" in str(e) or "does not exist" in str(e).lower():
            frappe.throw(
                "❌ The Item <b>Repair Service</b> does not exist in the system.<br>"
                "Please create this Item in Item Master before sending spare parts for repair."
            )

        # Generic fallback
        frappe.throw(
            f"❌ Failed to create Service Request.<br><br>"
            f"<b>Error:</b> {e}"
        )


# @frappe.whitelist()
# def find_linked_stock_entry(docname):
#     # #print('=================here is the row data-=========', data)
#     linked_stock_entry = frappe.db.get_list('Stock Entry Detail',filters={
#                             'custom_stock_item_move_reference':docname,
#                     },fields=["name","parent"],limit=1)
#     # doc.update(data)
    
#     # #print('===================here is the new spare move history doc ======================== ', linked_stock_entry)
#     # doc.insert(ignore_permissions=True)
#     return linked_stock_entry
