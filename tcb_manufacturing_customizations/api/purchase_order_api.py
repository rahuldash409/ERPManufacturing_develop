import frappe
from frappe import _


def get_warehouse_by_serial_no(serial_no):
    """Fetch warehouse for a given serial number from Serial and Batch Bundle"""
    warehouse = frappe.db.get_value(
        "Serial No",
        {"name": serial_no},
        "warehouse"
    )
    return warehouse

def get_warehouses_from_workstation_spares_settings():
    """Fetch default warehouses from Workstation Spare Parts Settings"""
    settings = frappe.get_single("Workstation Spares Settings")
    return settings


def check_draft_entries(po_name):
    # CHECK FOR DRAFT STOCK ENTRIES FIRST
    draft_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "custom_another_stock_entry_reference": po_name,
            "docstatus": 0  # Draft
        },
        fields=["name", "creation"],
        order_by="creation desc",
        limit=1
    )
    
    if draft_entries:
        draft_entry_name = draft_entries[0].name
        frappe.throw(
            title="Draft Stock Entry Exists",
            msg=f"""
                <div style="padding: 15px;">
                    <p style="font-size: 14px; margin-bottom: 15px;">
                        A <b>Draft Stock Entry</b> already exists for this Purchase Order.
                    </p>
                    
                    <div style="background: #fff3cd; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                        <b>Stock Entry:</b> <a href="/app/stock-entry/{draft_entry_name}" target="_blank">{draft_entry_name}</a>
                    </div>
                    
                    <p style="margin-bottom: 10px;"><b>Please complete one of the following actions:</b></p>
                    <ul style="margin-left: 20px;">
                        <li>Submit the draft Stock Entry to complete the transfer</li>
                        <li>Cancel the draft Stock Entry if not needed</li>
                    </ul>
                    
                    <p style="margin-top: 15px; color: #856404;">
                        <i class="fa fa-exclamation-triangle"></i> 
                        You cannot create a new Stock Entry until the existing draft is resolved.
                    </p>
                </div>
            """
        )



@frappe.whitelist()
def send_spares_to_repair_from_po(po_name):
    """Send only PENDING items to repair - Check for draft entries first"""
    
    po_doc = frappe.get_doc("Purchase Order", po_name)
    
    if po_doc.docstatus != 1:
        frappe.throw("Purchase Order must be submitted first")
    
    # CHECK FOR DRAFT STOCK ENTRIES FIRST
    check_draft_entries(po_name)
    
    # Get repair status
    status = get_po_repair_status(po_name)
    
    if not status['pending_to_send']:
        frappe.msgprint(
            title="No Items to Send",
            msg="All items have already been sent to repair warehouse.",
            indicator="blue"
        )
        return {
            "stock_entry_name": None,
            "items_count": 0,
            "message": "No pending items"
        }
    
    settings = frappe.get_single("Workstation Spares Settings")
    repair_warehouse = settings.default_repair_warehouse_for_repairables
    
    # Build stock items from PENDING items only
    stock_items = []
    for pending_item in status['pending_to_send']:
        item_uom = frappe.db.get_value('Item', pending_item['item_code'], 'stock_uom')
        from_wh = get_warehouse_by_serial_no(pending_item['serial_no'])
        
        stock_items.append({
            "item_code": pending_item['item_code'],
            "qty": 1,
            "uom": item_uom,
            "stock_uom": item_uom,
            "conversion_factor": 1,
            "s_warehouse": from_wh,
            "t_warehouse": repair_warehouse,
            "serial_no": pending_item['serial_no'],
            "use_serial_batch_fields": 1,
            "custom_stock_item_move_reference": pending_item['spare_ref']
        })
    
    if not stock_items:
        frappe.throw("No items found to transfer")
    
    # Create Stock Entry
    stock_entry = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "from_warehouse": stock_items[0]['s_warehouse'],
        "to_warehouse": repair_warehouse,
        "custom_another_stock_entry_reference": po_name,
        "custom_stock_entry_reference": "Workstation Spare Parts",
        "items": stock_items,
        "remarks": f"Items sent to Repair Warehouse for PO: {po_name}\n"
                   f"Created: {frappe.utils.now()}\n"
                   f"Items Count: {len(stock_items)}"
    })
    
    stock_entry.insert(ignore_permissions=True)
    
    # Update Move Histories
    for item in stock_entry.items:
        spare_move_history = frappe.get_list(
            "Spares Move History",
            filters={
                "spare_entry_reference": item.custom_stock_item_move_reference
            },
            fields=["name"],
            limit_page_length=1,
            order_by="creation desc"
        )
        
        if spare_move_history:
            mh_doc = frappe.get_doc("Spares Move History", spare_move_history[0].name)
            mh_doc.stock_entry_reference = stock_entry.name
            mh_doc.entry_date = stock_entry.posting_date
            mh_doc.save(ignore_permissions=True)
    
    frappe.db.commit()
    
    return {
        "stock_entry_name": stock_entry.name,
        "items_count": len(stock_items)
    }


@frappe.whitelist()
def create_return_stock_entry_from_po(po_name):
    """Receive only SENT BUT NOT RECEIVED items"""
    
    po_doc = frappe.get_doc("Purchase Order", po_name)
    
    if po_doc.docstatus != 1:
        frappe.throw("Purchase Order must be submitted first")
    
    check_draft_entries(po_name)
    
    
    sr_name = po_doc.custom_po_reference
    sr_doc = frappe.get_doc("Service Request", sr_name)
    
    # Get repair status
    status = get_po_repair_status(po_name)
    
    if not status['sent_but_not_received']:
        frappe.throw("No items in repair warehouse to receive")
    
    settings = frappe.get_single("Workstation Spares Settings")
    repair_warehouse = settings.default_repair_warehouse_for_repairables
    storage_warehouse = settings.default_storage_warehouse_for_repairables
    
    # Build stock items from SENT BUT NOT RECEIVED items only
    stock_items = []
    for item in status['sent_but_not_received']:
        item_uom = frappe.db.get_value('Item', item['item_code'], 'stock_uom')
        
        stock_items.append({
            "item_code": item['item_code'],
            "qty": 1,
            "uom": item_uom,
            "stock_uom": item_uom,
            "conversion_factor": 1,
            "s_warehouse": repair_warehouse,
            "t_warehouse": storage_warehouse,
            "serial_no": item['serial_no'],
            "use_serial_batch_fields": 1,
            "custom_stock_item_move_reference": item['spare_ref']
        })
    
    # Create Stock Entry
    stock_entry = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "from_warehouse": repair_warehouse,
        "to_warehouse": storage_warehouse,
        "custom_another_stock_entry_reference": po_name,
        "custom_stock_entry_reference": "Workstation Spare Parts",
        "items": stock_items,
        "remarks": f"Repaired items returned to stock from PO: {po_name}"
    })
    
    stock_entry.insert(ignore_permissions=True)
    
    # Create Move Histories
    new_move_histories = []
    for item in stock_entry.items:
        spare_doc = frappe.get_doc("Workstation Spare Parts", item.custom_stock_item_move_reference)
        new_mh = frappe.get_doc({
            "doctype": "Spares Move History",
            "spare_entry_reference": item.custom_stock_item_move_reference,
            "workstation": spare_doc.workstation,
            "spare_part": item.item_code,
            "from_warehouse": repair_warehouse,
            "to_warehouse": storage_warehouse,
            "entry_date": stock_entry.posting_date,
            "old_status": spare_doc.spare_status,
            "current_status": "Available",
            "stock_entry_reference": stock_entry.name,
            "asset_reference": spare_doc.asset_reference,
            "asset_repair_reference": sr_doc.asset_repair_reference,
            "item_serial_number": item.serial_no,
            "entry_details": f"Repaired item returned to stock\nStock Entry: {stock_entry.name}"
        })
        new_mh.insert(ignore_permissions=True)
        new_move_histories.append(new_mh.name)
    
    frappe.db.commit()
    
    return {
        "stock_entry_name": stock_entry.name,
        "items_count": len(stock_items),
        "new_move_histories": new_move_histories
    }


@frappe.whitelist()
def create_permanent_consumption_from_po(po_name):
    """Scrap only SENT BUT NOT RECEIVED items"""
    
    po_doc = frappe.get_doc("Purchase Order", po_name)
    
    if po_doc.docstatus != 1:
        frappe.throw("Purchase Order must be submitted first")
    
    check_draft_entries(po_name)
    
    sr_name = po_doc.custom_po_reference
    sr_doc = frappe.get_doc("Service Request", sr_name)
    
    # Get repair status
    status = get_po_repair_status(po_name)
    
    if not status['sent_but_not_received']:
        frappe.throw("No items in repair warehouse to scrap")
    
    settings = frappe.get_single("Workstation Spares Settings")
    repair_warehouse = settings.default_repair_warehouse_for_repairables
    
    # Build stock items from SENT BUT NOT RECEIVED items only
    stock_items = []
    for item in status['sent_but_not_received']:
        item_uom = frappe.db.get_value('Item', item['item_code'], 'stock_uom')
        
        stock_items.append({
            "item_code": item['item_code'],
            "qty": 1,
            "uom": item_uom,
            "stock_uom": item_uom,
            "conversion_factor": 1,
            "s_warehouse": repair_warehouse,
            "t_warehouse": "",
            "serial_no": item['serial_no'],
            "use_serial_batch_fields": 1,
            "custom_stock_item_move_reference": item['spare_ref']
        })
    
    # Create Stock Entry
    stock_entry = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Spares Permanent Consumption",
        "from_warehouse": repair_warehouse,
        "custom_another_stock_entry_reference": po_name,
        "custom_stock_entry_reference": "Workstation Spare Parts",
        "items": stock_items,
        "remarks": f"Permanent consumption of unrepairable items from PO: {po_name}"
    })
    
    stock_entry.insert(ignore_permissions=True)
    
    # Create Move Histories
    new_move_histories = []
    for item in stock_entry.items:
        spare_doc = frappe.get_doc("Workstation Spare Parts", item.custom_stock_item_move_reference)
        new_mh = frappe.get_doc({
            "doctype": "Spares Move History",
            "spare_entry_reference": item.custom_stock_item_move_reference,
            "workstation": spare_doc.workstation,
            "spare_part": item.item_code,
            "from_warehouse": repair_warehouse,
            "entry_date": stock_entry.posting_date,
            "old_status": spare_doc.spare_status,
            "current_status": "Scrapped",
            "stock_entry_reference": stock_entry.name,
            "asset_reference": spare_doc.asset_reference,
            "asset_repair_reference": sr_doc.asset_repair_reference,
            "item_serial_number": item.serial_no,
            "entry_details": f"Item scrapped\nStock Entry: {stock_entry.name}"
        })
        new_mh.insert(ignore_permissions=True)
        new_move_histories.append(new_mh.name)
    
    frappe.db.commit()
    
    return {
        "stock_entry_name": stock_entry.name,
        "items_count": len(stock_items),
        "new_move_histories": new_move_histories
    }



@frappe.whitelist()
def get_po_repair_status(po_name):
    """
    Track repair status of items in PO
    Returns: {
        total_items: int,
        sent_to_repair: int,
        received_from_repair: int,
        pending_items: [],
        sent_items: []
    }
    """
    
    # Get Move Histories for this PO
    move_histories = frappe.get_all(
        "Spares Move History",
        filters={
            "repair_po_reference": po_name
        },
        fields=["name", "spare_part", "item_serial_number", "spare_entry_reference"],
        limit_page_length=1000
    )
    
    if not move_histories:
        return {
            "total_items": 0,
            "sent_to_repair": 0,
            "received_from_repair": 0,
            "pending_to_send": [],
            "sent_but_not_received": []
        }
    
    total_items = len(move_histories)
    
    # Get repair warehouse from settings
    settings = frappe.get_single("Workstation Spares Settings")
    repair_warehouse = settings.default_repair_warehouse_for_repairables
    
    # Track sent items (items in submitted stock entries with t_warehouse = repair)
    sent_items = []
    sent_stock_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "custom_another_stock_entry_reference": po_name,
            "docstatus": 1
        },
        fields=["name"]
    )
    
    for se in sent_stock_entries:
        items = frappe.get_all(
            "Stock Entry Detail",
            filters={
                "parent": se.name,
                "t_warehouse": repair_warehouse
            },
            fields=["item_code", "serial_no", "custom_stock_item_move_reference"]
        )
        
        for item in items:
            if item.serial_no:
                sent_items.append({
                    "serial_no": item.serial_no,
                    "item_code": item.item_code,
                    "spare_ref": item.custom_stock_item_move_reference
                })
    
    # Track received items (items in submitted stock entries with s_warehouse = repair)
    received_items = []
    received_stock_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "custom_another_stock_entry_reference": po_name,
            "docstatus": 1
        },
        fields=["name"]
    )
    
    for se in received_stock_entries:
        items = frappe.get_all(
            "Stock Entry Detail",
            filters={
                "parent": se.name,
                "s_warehouse": repair_warehouse
            },
            fields=["item_code", "serial_no", "custom_stock_item_move_reference"]
        )
        
        for item in items:
            if item.serial_no:
                received_items.append({
                    "serial_no": item.serial_no,
                    "item_code": item.item_code,
                    "spare_ref": item.custom_stock_item_move_reference
                })
    
    # Find pending to send
    sent_serials = [item['serial_no'] for item in sent_items]
    pending_to_send = [
        {
            "serial_no": mh.item_serial_number,
            "item_code": mh.spare_part,
            "spare_ref": mh.spare_entry_reference
        }
        for mh in move_histories 
        if mh.item_serial_number not in sent_serials
    ]
    
    # Find sent but not received
    received_serials = [item['serial_no'] for item in received_items]
    sent_but_not_received = [
        item for item in sent_items 
        if item['serial_no'] not in received_serials
    ]
    
    return {
        "total_items": total_items,
        "sent_to_repair": len(sent_items),
        "received_from_repair": len(received_items),
        "pending_to_send": pending_to_send,
        "sent_but_not_received": sent_but_not_received
    }



@frappe.whitelist()
def get_items_to_send_for_repair(po_name):
    """Get pending items for dialog box selection"""
    status = get_po_repair_status(po_name)
    
    if not status['pending_to_send']:
        return []
    
    items_list = []
    for item in status['pending_to_send']:
        # Get item details
        item_doc = frappe.get_doc('Workstation Spare Parts', item['spare_ref'])
        
        items_list.append({
            'spare_id': item['spare_ref'],
            'item_code': item['item_code'],
            'item_name': frappe.db.get_value('Item', item['item_code'], 'item_name'),
            'serial_no': item['serial_no'],
            'workstation': item_doc.workstation,
            'current_warehouse': get_warehouse_by_serial_no(item['serial_no'])
        })
    
    return items_list


@frappe.whitelist()
def get_items_to_receive_from_repair(po_name):
    """Get items ready to receive for dialog box selection"""
    status = get_po_repair_status(po_name)
    
    if not status['sent_but_not_received']:
        return []
    
    items_list = []
    for item in status['sent_but_not_received']:
        item_doc = frappe.get_doc('Workstation Spare Parts', item['spare_ref'])
        
        items_list.append({
            'spare_id': item['spare_ref'],
            'item_code': item['item_code'],
            'item_name': frappe.db.get_value('Item', item['item_code'], 'item_name'),
            'serial_no': item['serial_no'],
            'workstation': item_doc.workstation,
            'current_warehouse': get_warehouse_by_serial_no(item['serial_no'])
        })
    
    return items_list


@frappe.whitelist()
def send_selected_spares_to_repair(po_name, selected_spare_ids):
    """Send only selected items to repair"""
    import json
    
    if isinstance(selected_spare_ids, str):
        selected_spare_ids = json.loads(selected_spare_ids)
    
    if not selected_spare_ids:
        frappe.throw("No items selected")
    
    po_doc = frappe.get_doc("Purchase Order", po_name)
    
    if po_doc.docstatus != 1:
        frappe.throw("Purchase Order must be submitted first")
    
    check_draft_entries(po_name)
    
    settings = frappe.get_single("Workstation Spares Settings")
    repair_warehouse = settings.default_repair_warehouse_for_repairables
    
    # Build stock items from selected spares only
    stock_items = []
    for spare_id in selected_spare_ids:
        spare_doc = frappe.get_doc('Workstation Spare Parts', spare_id)
        item_uom = frappe.db.get_value('Item', spare_doc.spare_part, 'stock_uom')
        from_wh = get_warehouse_by_serial_no(spare_doc.item_serial_number)
        
        stock_items.append({
            "item_code": spare_doc.spare_part,
            "qty": 1,
            "uom": item_uom,
            "stock_uom": item_uom,
            "conversion_factor": 1,
            "s_warehouse": from_wh,
            "t_warehouse": repair_warehouse,
            "serial_no": spare_doc.item_serial_number,
            "use_serial_batch_fields": 1,
            "custom_stock_item_move_reference": spare_id
        })
    
    if not stock_items:
        frappe.throw("No items found to transfer")
    
    # Create Stock Entry
    stock_entry = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "from_warehouse": stock_items[0]['s_warehouse'],
        "to_warehouse": repair_warehouse,
        "custom_another_stock_entry_reference": po_name,
        "custom_stock_entry_reference": "Workstation Spare Parts",
        "items": stock_items,
        "remarks": f"Selected items sent to Repair Warehouse for PO: {po_name}\n"
                   f"Items Count: {len(stock_items)}\n"
                   f"Spare IDs: {', '.join(selected_spare_ids[:5])}{'...' if len(selected_spare_ids) > 5 else ''}"
    })
    
    stock_entry.insert(ignore_permissions=True)
    
    # Update Move Histories for selected items only
    for spare_id in selected_spare_ids:
        spare_move_history = frappe.get_list(
            "Spares Move History",
            filters={
                "spare_entry_reference": spare_id
            },
            fields=["name"],
            limit_page_length=1,
            order_by="creation desc"
        )
        
        if spare_move_history:
            mh_doc = frappe.get_doc("Spares Move History", spare_move_history[0].name)
            mh_doc.stock_entry_reference = stock_entry.name
            mh_doc.entry_date = stock_entry.posting_date
            mh_doc.save(ignore_permissions=True)
    
    frappe.db.commit()
    
    return {
        "stock_entry_name": stock_entry.name,
        "items_count": len(stock_items)
    }


@frappe.whitelist()
def receive_selected_spares_from_repair(po_name, selected_spare_ids, action_type):
    """
    Receive selected items from repair
    action_type: 'return' or 'scrap'
    """
    import json
    
    if isinstance(selected_spare_ids, str):
        selected_spare_ids = json.loads(selected_spare_ids)
    
    if not selected_spare_ids:
        frappe.throw("No items selected")
    
    po_doc = frappe.get_doc("Purchase Order", po_name)
    
    if po_doc.docstatus != 1:
        frappe.throw("Purchase Order must be submitted first")
    
    check_draft_entries(po_name)
    
    sr_name = po_doc.custom_po_reference
    sr_doc = frappe.get_doc("Service Request", sr_name)
    
    settings = frappe.get_single("Workstation Spares Settings")
    repair_warehouse = settings.default_repair_warehouse_for_repairables
    storage_warehouse = settings.default_storage_warehouse_for_repairables
    
    # Build stock items
    stock_items = []
    for spare_id in selected_spare_ids:
        spare_doc = frappe.get_doc('Workstation Spare Parts', spare_id)
        item_uom = frappe.db.get_value('Item', spare_doc.spare_part, 'stock_uom')
        
        stock_items.append({
            "item_code": spare_doc.spare_part,
            "qty": 1,
            "uom": item_uom,
            "stock_uom": item_uom,
            "conversion_factor": 1,
            "s_warehouse": repair_warehouse,
            "t_warehouse": storage_warehouse if action_type == 'return' else "",
            "serial_no": spare_doc.item_serial_number,
            "use_serial_batch_fields": 1,
            "custom_stock_item_move_reference": spare_id
        })
    
    # Create Stock Entry
    if action_type == 'return':
        stock_entry_type = "Material Transfer"
        remarks = f"Selected repaired items returned to stock from PO: {po_name}"
        new_status = "Available"
    else:  # scrap
        stock_entry_type = "Spares Permanent Consumption"
        remarks = f"Selected items scrapped from PO: {po_name}"
        new_status = "Scrapped"
    
    stock_entry = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": stock_entry_type,
        "from_warehouse": repair_warehouse,
        "to_warehouse": storage_warehouse if action_type == 'return' else None,
        "custom_another_stock_entry_reference": po_name,
        "custom_stock_entry_reference": "Workstation Spare Parts",
        "items": stock_items,
        "remarks": remarks
    })
    
    stock_entry.insert(ignore_permissions=True)
    
    # Create Move Histories
    new_move_histories = []
    for spare_id in selected_spare_ids:
        spare_doc = frappe.get_doc("Workstation Spare Parts", spare_id)
        
        new_mh = frappe.get_doc({
            "doctype": "Spares Move History",
            "spare_entry_reference": spare_id,
            "workstation": spare_doc.workstation,
            "spare_part": spare_doc.spare_part,
            "from_warehouse": repair_warehouse,
            "to_warehouse": storage_warehouse if action_type == 'return' else "",
            "entry_date": stock_entry.posting_date,
            "old_status": spare_doc.spare_status,
            "current_status": new_status,
            "stock_entry_reference": stock_entry.name,
            "asset_reference": spare_doc.asset_reference,
            "asset_repair_reference": sr_doc.asset_repair_reference,
            "item_serial_number": spare_doc.item_serial_number,
            "entry_details": f"Item {action_type}ed\nStock Entry: {stock_entry.name}"
        })
        new_mh.insert(ignore_permissions=True)
        new_move_histories.append(new_mh.name)
    
    frappe.db.commit()
    
    return {
        "stock_entry_name": stock_entry.name,
        "items_count": len(stock_items),
        "new_move_histories": new_move_histories
    }
