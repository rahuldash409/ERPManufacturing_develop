import frappe


@frappe.whitelist()
def get_qc_status(qc_doc):
    qc = frappe.get_doc("Quality Inspection",qc_doc)
    
    flag = False
    if any (r.status =="Rejected" for r in qc.readings):
        qc.custom_on_hold = 1
        qc.save()
        flag = True
        
    elif not any (r.status == "Rejected" for r in qc.readings):
        qc.custom_on_hold = 0
        qc.save()
        flag = False
    frappe.db.commit
    
    if flag:
        return "Confirmed"
    if not flag:
        return "Nothing"
    

# @frappe.whitelist()
# def get_stock_entry_items(stock_entry_name):
#     """Get all items from a stock entry with full details"""
#     doc = frappe.get_doc("Stock Entry", stock_entry_name)
    
#     items = []
#     for item in doc.items:
#         items.append({
#             "item_code": item.item_code,
#             "item_name": item.item_name,
#             "qty": item.qty,
#             "uom": item.uom,
#             "conversion_factor":item.conversion_factor,
#             "transfer_qty":item.transfer_qty,
#             "custom_workstation":item.custom_workstation,
#             "item_group": item.item_group,
#             "s_warehouse": item.s_warehouse,
#             "t_warehouse": item.t_warehouse,
#             "serial_no": item.serial_no,
#             "custom_select_serial_no": item.custom_select_serial_no
#         })
#     # print('====================== items ===',item)
#     return items

@frappe.whitelist()
def get_stock_entry_items(stock_entry_name):
    """
    Get all items from a stock entry with full details
    - Expands Repairable Spares into separate lines based on serial numbers
    - Fetches serial numbers from serial_and_batch_bundle if serial_no is empty
    """
    doc = frappe.get_doc("Stock Entry", stock_entry_name)
    items = []
    
    for item in doc.items:
        # Get serial numbers
        serial_numbers = []
        
        # Method 1: Check serial_no field (comma-separated)
        if item.serial_no:
            serial_numbers = [s.strip() for s in item.serial_no.split('\n') if s.strip()]
        
        # Method 2: Check serial_and_batch_bundle if serial_no is empty
        elif item.serial_and_batch_bundle:
            bundle_doc = frappe.get_doc("Serial and Batch Bundle", item.serial_and_batch_bundle)
            if bundle_doc.entries:
                # Get first serial number from bundle entries
                serial_numbers = [entry.serial_no for entry in bundle_doc.entries if entry.serial_no]
        
        # Check if item is Repairable Spares and has serial numbers
        if item.item_group == "Repairable Spares" and serial_numbers:
            # Create separate line for each serial number
            for serial_no in serial_numbers:
                items.append({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "qty": 1,  # One item per serial number
                    "uom": item.uom,
                    "conversion_factor": item.conversion_factor,
                    "transfer_qty": item.transfer_qty,
                    "custom_workstation": item.custom_workstation,
                    "item_group": item.item_group,
                    "s_warehouse": item.s_warehouse,
                    "t_warehouse": item.t_warehouse,
                    "serial_no": serial_no,
                    "custom_select_serial_no": serial_no,
                    "serial_and_batch_bundle": None,
                    "custom_stock_item_move_reference": item.custom_stock_item_move_reference
                })
        else:
            # Non-repairable or no serial numbers - add as single line
            items.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": item.qty,
                "uom": item.uom,
                "conversion_factor": item.conversion_factor,
                "transfer_qty": item.transfer_qty,
                "custom_workstation": item.custom_workstation,
                "item_group": item.item_group,
                "s_warehouse": item.s_warehouse,
                "t_warehouse": item.t_warehouse,
                "serial_no": item.serial_no or (serial_numbers[0] if serial_numbers else None),
                "custom_select_serial_no": item.custom_select_serial_no or (serial_numbers[0] if serial_numbers else None),
                "serial_and_batch_bundle": item.serial_and_batch_bundle,
                # "custom_stock_item_move_reference": item.custom_stock_item_move_reference
                
            })
    
    return items