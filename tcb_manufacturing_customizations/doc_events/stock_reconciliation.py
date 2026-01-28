import frappe
import time

def sync_sub_batch(doc, method=None):
    time.sleep(1)
    for item in doc.items:
        if item.use_serial_batch_fields and item.custom_sub_batch:
            latest_batch = frappe.db.get_all("Batch",filters={"item":item.item_code},order_by = "creation desc",fields = ["name"],limit=1)
            for batches in latest_batch:
                batch = frappe.get_doc("Batch",batches.name)
                sub_batch = batch.custom_sub_batch or None
                if not sub_batch:
                    frappe.db.set_value("Batch",batches.name,"custom_sub_batch",item.custom_sub_batch)
            
    frappe.db.commit()