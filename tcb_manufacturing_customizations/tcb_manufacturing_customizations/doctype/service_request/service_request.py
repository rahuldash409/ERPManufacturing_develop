# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

from frappe.model.document import Document
import frappe
from frappe import _


class ServiceRequest(Document):
    pass


@frappe.whitelist()
def update_move_histories_on_approval(sr_name):
    """Update all related Move Histories when SR is approved/submitted"""
    
    move_histories = frappe.get_all(
        "Spares Move History",
        filters={
            "service_request_reference": sr_name
        },
        fields=["name"],
        limit_page_length=1000
    )
    
    if not move_histories:
        frappe.msgprint(_("No Move Histories found for this Service Request"))
        return {"count": 0}
    
    count = 0
    for mh in move_histories:
        doc = frappe.get_doc("Spares Move History", mh.name)
        doc.is_service_request_submitted = 1
        doc.is_service_request_rejected = 0
        doc.save(ignore_permissions=True)
        count += 1
    
    frappe.db.commit()
    # print(["==================== Updated Move Histories on SR Approval:", count])
    return {"count": count, "message": f"Updated {count} Move History records"}


@frappe.whitelist()
def update_move_histories_on_rejection(sr_name):
    """Update all related Move Histories when SR is rejected (legacy function)"""
    
    move_histories = frappe.get_all(
        "Spares Move History",
        filters={
            "service_request_reference": sr_name
        },
        fields=["name"],
        limit_page_length=1000
    )
    
    if not move_histories:
        frappe.msgprint(_("No Move Histories found for this Service Request"))
        return {"count": 0}
    
    count = 0
    for mh in move_histories:
        doc = frappe.get_doc("Spares Move History", mh.name)
        doc.is_service_request_rejected = 1
        doc.is_service_request_submitted = 0
        doc.save(ignore_permissions=True)
        count += 1
    
    frappe.db.commit()
    
    return {"count": count, "message": f"Marked {count} Move History records as rejected"}


#  UPDATED: Rejection with spares return
@frappe.whitelist()
def reject_service_request_with_spares_return(sr_name, return_status, rejection_reason):
    """
    Reject SR and return spares based on user selection
    return_status: 'Available' or 'In Use'
    """
    
    sr_doc = frappe.get_doc("Service Request", sr_name)
    
    if sr_doc.docstatus == 2:
        frappe.throw("Service Request is already cancelled/rejected")
    
    # Get Move Histories
    move_histories = frappe.get_all(
        "Spares Move History",
        filters={
            "service_request_reference": sr_name
        },
        fields=["*"],
        limit_page_length=1000
    )
    
    if not move_histories:
        frappe.throw("No Move Histories found for this Service Request")
    
    # Get settings
    settings = frappe.get_single("Workstation Spares Settings")
    storage_warehouse = settings.default_storage_warehouse_for_repairables
    
    # Determine new status based on return_status
    if return_status == "Available":
        new_status = "Available"
    else:  # In Use
        new_status = "In Use"
    
    # Build stock items based on return status
    stock_items = []
    for mh in move_histories:
        spare_doc = frappe.get_doc("Workstation Spare Parts", mh.spare_entry_reference)
        
        # Get current warehouse from serial number
        from_warehouse = get_warehouse_by_serial_no(mh.item_serial_number)
        
        # Determine target warehouse based on return status
        if return_status == "Available":
            to_warehouse = storage_warehouse
        else:  # In Use
            # Get workstation warehouse
            workstation_doc = frappe.get_doc("Workstation", spare_doc.workstation)
            to_warehouse = workstation_doc.warehouse
        
        item_uom = frappe.db.get_value('Item', mh.spare_part, 'stock_uom')
        
        stock_items.append({
            "item_code": mh.spare_part,
            "qty": 1,
            "uom": item_uom,
            "stock_uom": item_uom,
            "conversion_factor": 1,
            "s_warehouse": from_warehouse,
            "t_warehouse": to_warehouse,
            "serial_no": mh.item_serial_number,
            "use_serial_batch_fields": 1,
            "custom_stock_item_move_reference": mh.spare_entry_reference
        })
    
    if not stock_items:
        frappe.throw("No items found to return")
    
    #  Create Stock Entry
    stock_entry = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "asset_repair":sr_doc.asset_repair_reference,
        "from_warehouse": stock_items[0]['s_warehouse'],
        "to_warehouse": stock_items[0]['t_warehouse'],
        "custom_another_stock_entry_reference": sr_name,
        "custom_stock_entry_reference": "Workstation Spare Parts",
        "items": stock_items,
        "remarks": f"Service Request {sr_name} REJECTED\n"
                f"Return Status: {return_status}\n"
                f"Reason: {rejection_reason}\n"
                f"Items returned from Damaged to {return_status} status"
    })
    
    stock_entry.insert(ignore_permissions=True)
    # stock_entry.submit()
    
    #  Update existing Move Histories with rejection flag
    for mh in move_histories:
        mh_doc = frappe.get_doc("Spares Move History", mh.name)
        mh_doc.is_service_request_rejected = 1
        mh_doc.is_service_request_submitted = 0
        mh_doc.ignored_history = 1
        # mh_doc.stock_entry_reference = stock_entry.name
        # mh_doc.entry_date = stock_entry.posting_date
        mh_doc.save(ignore_permissions=True)
    
    #  Create NEW Move Histories for the return transaction
    new_move_histories = []
    for item_row in stock_entry.items:
        spare_doc = frappe.get_doc("Workstation Spare Parts", item_row.custom_stock_item_move_reference)
        
        # Get old status from spare doc (before status change)
        old_status = spare_doc.spare_status
        
        new_mh = frappe.get_doc({
            "doctype": "Spares Move History",
            "spare_entry_reference": item_row.custom_stock_item_move_reference,
            "workstation": spare_doc.workstation,
            "spare_part": item_row.item_code,
            "from_warehouse": item_row.s_warehouse,
            "to_warehouse": item_row.t_warehouse,
            "entry_date": stock_entry.posting_date,
            "old_status": old_status,
            "current_status": new_status,
            "stock_entry_reference": stock_entry.name,
            "asset_reference": spare_doc.asset_reference,
            # "service_request_reference": sr_name,
            "item_serial_number": item_row.serial_no,
            # "is_service_request_rejected": 1,
            "entry_details": f"Service Request Rejected\nReason: {rejection_reason}\nReturned to {return_status} status"
        })
        new_mh.insert(ignore_permissions=True)
        new_move_histories.append(new_mh.name)
    
    #  Add comment to SR
    sr_doc.add_comment(
        "Comment",
        text=f"<b>❌ Rejected</b><br>"
            f"Return Status: {return_status}<br>"
            f"Reason: {rejection_reason}<br>"
            f"Stock Entry: <a href='/app/stock-entry/{stock_entry.name}'>{stock_entry.name}</a><br>"
            f"Items Returned: {len(stock_items)}<br>"
            f"New Move Histories Created: {len(new_move_histories)}"
    )
    
    #  Update SR workflow state and docstatus
    sr_doc.workflow_state = "Rejected"
    sr_doc.docstatus = 2  # Cancelled
    sr_doc.save(ignore_permissions=True)
    
    frappe.db.commit()
    
    return {
        "success": True,
        "stock_entry_name": stock_entry.name,
        "items_count": len(stock_items),
        "move_history_count": len(new_move_histories),
        "new_move_histories": new_move_histories,
        "message": f"Service Request rejected and {len(stock_items)} items returned"
    }


def get_warehouse_by_serial_no(serial_no):
    """Fetch warehouse for a given serial number"""
    warehouse = frappe.db.get_value(
        "Serial No",
        {"name": serial_no},
        "warehouse"
    )
    return warehouse


def get_existing_po_for_sr(sr_name):
    po = frappe.get_all(
        "Purchase Order",
        filters={
            "custom_po_reference": sr_name,
            "docstatus": ["!=", 2]
        },
        fields=["name", "docstatus"],
        limit_page_length = 1
    )
    return po[0] if po else None


@frappe.whitelist()
def create_po_from_sr(sr_name):
    sr_doc = frappe.get_doc("Service Request", sr_name)

    if sr_doc.docstatus != 1:
        frappe.throw("Service Request must be submitted first")

    existing_po = get_existing_po_for_sr(sr_name)

    if existing_po:
        if existing_po.docstatus == 0:
            frappe.throw(
                f"A Draft Purchase Order <b>{existing_po.name}</b> already exists. "
                "Please complete or submit that PO."
            )
        elif existing_po.docstatus == 1:
            frappe.throw(
                f"A Submitted Purchase Order <b>{existing_po.name}</b> already exists. "
                "Only one PO is allowed per Service Request. "
                "Cancel it to create a new one."
            )
    
    # Build PO items
    po_items = []
    for item_row in sr_doc.service_request_item_details:
        po_items.append({
            "item_code": item_row.item,
            "item_name": item_row.item_name,
            "qty": item_row.qty,
            "rate": item_row.rate,
            "description": item_row.remarks or item_row.description,
            "custom_item_to_repair": item_row.linked_item,
            "schedule_date": sr_doc.schedule_date
        })
    
    # Create PO
    po_doc = frappe.get_doc({
        "doctype": "Purchase Order",
        "supplier": sr_doc.supplier,
        "schedule_date": sr_doc.schedule_date if sr_doc.schedule_date else sr_doc.date,
        "transaction_date": sr_doc.date,
        "custom_reference_document": sr_doc.doctype,
        "items": po_items,
        "remarks": f"Created from Service Request: {sr_name}\n{sr_doc.remarks or ''}",
        "custom_po_reference": sr_name
    })
    
    po_doc.insert(ignore_permissions=True)
    
    if po_doc:
        sr_doc.po_created = 1
        sr_doc.save(ignore_permissions=True)
    
    # Update Move Histories with PO reference
    move_histories = frappe.get_all(
        "Spares Move History",
        filters={
            "service_request_reference": sr_name
        },
        fields=["name"],
        limit_page_length=1000
    )
    
    move_history_count = 0
    for mh in move_histories:
        mh_doc = frappe.get_doc("Spares Move History", mh.name)
        mh_doc.repair_po_reference = po_doc.name
        mh_doc.save(ignore_permissions=True)
        move_history_count += 1
    
    frappe.db.commit()
    
    return {
        "po_name": po_doc.name,
        "move_history_count": move_history_count
    }
