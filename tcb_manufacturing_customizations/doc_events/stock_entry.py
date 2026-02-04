import math
from collections import defaultdict

import frappe
from erpnext.stock.doctype.batch.batch import get_batch_qty
from frappe import _
from frappe.utils import flt, now, nowdate, today


def update_batches(doc, method=None):
    if not doc.items:
        return
    for item in doc.items:
        if not item.custom_sub_batch and item.batch_no and not item.is_finished_item:
            ba = frappe.get_doc("Batch", item.batch_no)
            if ba.custom_sub_batch:
                item.custom_sub_batch = ba.custom_sub_batch




# SET CONTAINER DATA ON MATERIAL RECEIPT
def materialreceipt(doc,method=None):
    if doc.stock_entry_type =="Material Receipt":
        frappe.enqueue(
            method = setbatchesafterreceipt,
            docname = doc.name,
            enqueue_after_commit = True
        )

def setbatchesafterreceipt(docname,method=None):
    se = frappe.get_doc("Stock Entry",docname)
    if se.items:
        for item in se.items:
            if item.custom_sub_batch:
                if item.serial_and_batch_bundle:
                    ba_bundle = frappe.get_doc("Serial and Batch Bundle", item.serial_and_batch_bundle)
                    for entry in ba_bundle.entries:
                        if entry.batch_no:
                            batch = frappe.get_doc("Batch", entry.batch_no)
                            if not batch.custom_sub_batch:
                                batch.custom_sub_batch = item.custom_sub_batch
                                batch.custom_container_name= item.custom_container_name or ""
                                batch.custom_container_number= item.custom_container_number or ""
                                batch.save()
                    frappe.db.commit()
            if not item.custom_sub_batch:
                if item.serial_and_batch_bundle:
                    ba_bundle = frappe.get_doc("Serial and Batch Bundle", item.serial_and_batch_bundle)
                    for entry in ba_bundle.entries:
                        if entry.batch_no:
                            batch = frappe.get_doc("Batch", entry.batch_no)
                            if not batch.custom_sub_batch:
                                batch.custom_sub_batch = batch.name
                                batch.custom_container_name= item.custom_container_name or ""
                                batch.custom_container_number= item.custom_container_number or ""
                                batch.save()
                    frappe.db.commit()



# WHEN THE STOCK ENTRY SUBMITS,, FLAG A CHECK IN JOB CARD IF EXISTS THAT IT NEEDS A RELOAD
def flagJc(doc,method=None):
    if doc.job_card:
        frappe.db.set_value("Job Card",doc.job_card,"custom_need_document_refresh",1)
        frappe.db.sql("""
                DELETE FROM `tabJob Card Material Consumption`
                WHERE parent = %s
            """, doc.job_card)
        frappe.db.sql("""
                DELETE FROM `tabJob Card Material Consumption Slitting`
                WHERE parent = %s
            """, doc.job_card)
        frappe.db.sql("""
                DELETE FROM `tabJob Card Material Consumption ADSTAR`
                WHERE parent = %s
            """, doc.job_card)

        frappe.db.commit()


@frappe.whitelist()
def set_sb_after_submit(docname, method=None):
    doc = frappe.get_doc("Stock Entry", docname)
    if (
        not doc.stock_entry_type == "Manufacture"
        and not doc.stock_entry_type == "Material Receipt"
    ):
        return
    if not doc.items:
        return

    # Track batches to update - avoid saving same batch multiple times
    # Collect all batch updates first, then save once per batch
    batches_to_update = {}

    for item in doc.items:
        if item.serial_and_batch_bundle and item.custom_sub_batch:
            b_bundle = frappe.get_doc("Serial and Batch Bundle", item.serial_and_batch_bundle)
            if b_bundle.entries:
                for entry in b_bundle.entries:
                    if entry.batch_no and entry.batch_no not in batches_to_update:
                        batches_to_update[entry.batch_no] = {
                            "custom_sub_batch": item.custom_sub_batch,
                            "custom_segregated_item_qty": flt(item.custom_segregated_item_qty) or 0,
                            "description": item.custom_sub_batches_used or ""
                        }
        elif item.serial_and_batch_bundle and not item.custom_sub_batch:
            b_bundle = frappe.get_doc("Serial and Batch Bundle", item.serial_and_batch_bundle)
            if b_bundle.entries:
                for entry in b_bundle.entries:
                    if entry.batch_no and entry.batch_no not in batches_to_update:
                        batches_to_update[entry.batch_no] = {
                            "custom_sub_batch": entry.batch_no,  # Use batch name as sub_batch
                            "custom_segregated_item_qty": flt(item.custom_segregated_item_qty) or 0,
                            "description": item.custom_sub_batches_used or ""
                        }

    # Now save each batch once using direct SQL to avoid record changed error
    for batch_no, update_data in batches_to_update.items():
        # Check if batch already has custom_sub_batch
        existing_sub_batch = frappe.db.get_value("Batch", batch_no, "custom_sub_batch")
        if not existing_sub_batch:
            # Use direct SQL UPDATE to avoid "Record has changed since last read" error
            frappe.db.sql("""
                UPDATE `tabBatch`
                SET
                    custom_sub_batch = %(custom_sub_batch)s,
                    custom_segregated_item_qty = %(custom_segregated_item_qty)s,
                    description = %(description)s
                WHERE name = %(batch_no)s
            """, {
                "custom_sub_batch": update_data["custom_sub_batch"],
                "custom_segregated_item_qty": update_data["custom_segregated_item_qty"],
                "description": update_data["description"],
                "batch_no": batch_no
            })


# def set_sub_batch(doc,method=None):
#     if doc.stock_entry_type=="Material Transfer for Manufacture":
#         if doc.items:
#             for item in doc.items:
#                 if item.get("custom_sub_batch"):
#                     batch_ = frappe.get_list("Batch",filters={"custom_sub_batch":item.custom_sub_batch,"item":item.item_code},pluck="name")
#                     found = False
#                     if not batch_:
#                         frappe.throw(f"No Batch found for item <b>{item.item_code}</b> with Sub Batch <b>{item.custom_sub_batch}</b>")
#                     for batch in batch_:
#                         qty = get_batch_qty(batch,item.s_warehouse,item.item_code)
#                         if qty>=item.qty:
#                             item.batch_no = batch
#                             found=True
#                             break
#                     if not found:
#                         frappe.throw(f"No Batch found with enough quantity for item <b>{item.item_code}</b>")


def set_finished_good_qty(doc, method=None):
    if doc.items and doc.work_order and doc.stock_entry_type == "Manufacture":
        wo = frappe.get_doc("Work Order", doc.work_order)
        if "slitting" in [op.operation.lower() for op in wo.operations]:
            qty = wo.qty
            req_qty = sum(r.required_qty for r in wo.required_items)
            div = qty / req_qty if req_qty else 1
        count = sum(
            1
            for item in doc.items
            if ("patch" in item.item_name.lower() or "valve" in item.item_name.lower() or "flat" in item.item_name.lower()) and not item.is_finished_item
        )
        final_items = [item.name for item in doc.items if item.is_finished_item]
        # roll_division = wo.custom_roll_division or 1
        return count, final_items, div if div else 1
                
                
@frappe.whitelist()
def set_finished_goods(docname):
    doc = frappe.get_doc("Stock Entry",docname)
    count, final_items, div = set_finished_good_qty(doc)

    finished_items = [item.as_dict() for item in doc.items if item.name in final_items]
    fabric_qtys = [item.qty for item in doc.items if ("patch" in item.item_name.lower() or "valve" in item.item_name.lower() or "flat" in item.item_name.lower()) and not item.is_finished_item]
    fabric_sub_batch = [item.custom_sub_batch for item in doc.items if ("patch" in item.item_name.lower() or "valve" in item.item_name.lower() or "flat" in item.item_name.lower()) and not item.is_finished_item]
    fabric_slit_cutlengths = [item.custom_slitec_roll_cutlengths for item in doc.items if ("patch" in item.item_name.lower() or "valve" in item.item_name.lower() or "flat" in item.item_name.lower()) and not item.is_finished_item]
  
    return {
        "finished_items": finished_items,
        "fabric_qtys": fabric_qtys,
        "div": math.ceil(div),
        "sub_batch":fabric_sub_batch,
        # "roll_division":roll_division
        "cut_lengths":fabric_slit_cutlengths
    }


# def after_submit(doc,method=None):
#     frappe.log_error("Running after submit-----------------")
#     if doc.items and doc.stock_entry_type=="Manufacture":
#         ##print("-------------------------------",doc.items)
#         for item in doc.items:
#             if item.custom_sub_batch and item.use_serial_batch_fields:
#                 ##print("CUSTOM BATCH -----------------------",item.custom_batch)
#                 bb = item.serial_and_batch_bundle
#                 ##print("BBBBBBBBBBBBBBBB---------",bb)
#                 if bb:
#                     batch_b = frappe.get_doc("Serial and Batch Bundle",bb)
#                     ##print("-------------------------------------batch b-------------",batch_b)
#                     if batch_b.entries:
#                         for entry in batch_b.entries:
#                             if entry.batch_no:
#                                 batch = frappe.get_doc("Batch",entry.batch_no)
#                                 if not batch.custom_sub_batch:
#                                     batch.custom_sub_batch = item.custom_sub_batch
#                                     batch.save()
#     frappe.db.commit()


# def split_final_product(doc,method=None):
#     if doc.stock_entry_type == "Manufacture" and doc.work_order:
#         wo = frappe.get_doc("Work Order",doc.work_order if doc.work_order else "")
#         op = any("Slitting" not in opn.operation and "Bag Manufacturing" not in opn.operation and "Segregation" not in opn.operation
#                 and "Packaging" not in opn.operation for opn in wo.operations if wo.operations)
#         if op:
#             fabrics = [item for item in doc.items if "fabric" in item.item_name.lower() and not item.is_finished_item]
#             finished_goods = [item for item in doc.items if item.is_finished_item and not item.get("custom_split_from_fabric")]

#             to_remove = []

#             if len(fabrics)>1:
#                 for finished_item in finished_goods:
#                     to_remove.append(finished_item.idx)
#                     for fabric in fabrics:
#                         new_row = doc.append("items",{})

#                         for key in finished_item.as_dict():
#                             if key not in ["name","idx","custom_sub_batch"]:
#                                 new_row.set(key,finished_item.get(key))
#                                 new_row.set("qty",fabric.qty)
#                                 new_row.set("custom_sub_batch",fabric.custom_sub_batch if fabric.custom_sub_batch else "")
#                                 new_row.set("custom_split_from_fabric", True)
#             else:
#                 for finished_item in finished_goods:
#                     to_remove.append(finished_item.idx)
#                     for fabric in fabrics:
#                         new_row = doc.append("items",{})

#                         for key in finished_item.as_dict():
#                             if key not in ["name","idx","custom_sub_batch"]:
#                                 new_row.set(key,finished_item.get(key))
#                                 new_row.set("custom_sub_batch",fabric.custom_sub_batch if fabric.custom_sub_batch else "")
#                                 new_row.set("custom_split_from_fabric", True)

#             for item in doc.items:
#                 if item.idx in to_remove:
#                     doc.remove(item)

#         if not op:
#             fabrics = [item for item in doc.items if ("main body" in item.item_name.lower() or "bags" in item.item_group.lower()) and not item.is_finished_item]
#             fabric_sum = sum(item.qty for item in doc.items if ("main body" in item.item_name.lower() or "bags" in item.item_group.lower()) and not item.is_finished_item)
#             finished_goods = [item for item in doc.items if item.is_finished_item and "slitec" not in item.item_name.lower() and not item.get("custom_split_from_fabric")]
#             to_remove = []
#             # work_order = frappe.db.get_value("Work Order",doc.work_order,"qty")
#             if len(fabrics)>1:
#                 for finished_item in finished_goods:
#                     # THIS IS FOR WHEN WE WANT THE AD*STAR BAG TO HAVE BATCHES OF MAIN BODY BUT QTY BE DIVIDED AMONG NUMBER OF BATCHES
#                     # division = int(finished_item.qty/len(fabrics))
#                     to_remove.append(finished_item.idx)
#                     for fabric in fabrics:
#                         fabric_perc = (fabric.qty/fabric_sum)*100
#                         new_row = doc.append("items",{})
#                         for key in finished_item.as_dict():
#                             if key not in ["name","idx","custom_sub_batch"]:
#                                 new_row.set(key,finished_item.get(key))
#                                 new_row.set("qty",int(doc.fg_completed_qty * (fabric_perc/100)))
#                                 new_row.set("custom_sub_batch",fabric.custom_sub_batch if fabric.custom_sub_batch else "")
#                                 new_row.set("custom_split_from_fabric", True)
#             else:
#                 for finished_item in finished_goods:
#                     item = frappe.get_doc("Item",finished_item.item_code)
#                     if item.has_batch_no and "pkg" not in finished_item.item_name.lower() and "fg" not in finished_item.item_name.lower():
#                         to_remove.append(finished_item.idx)
#                         for fabric in fabrics:
#                             new_row = doc.append("items",{})
#                             for key in finished_item.as_dict():
#                                 if key not in ["name","idx","custom_sub_batch"]:
#                                     new_row.set(key,finished_item.get(key))
#                                     new_row.set("custom_sub_batch",fabric.custom_sub_batch if fabric.custom_sub_batch else "")
#                                     new_row.set("custom_split_from_fabric", True)
#             for item in doc.items:
#                 if item.idx in to_remove:
#                     doc.remove(item)

# doc.save()


# THIS LOGIC IS MORE COMPLEX AND REDUNDANT, THATS WHY COMMENTED
# final_item = defaultdict(list)
# for item in doc.items:
#     if item.is_finished_item:
#         final_item[item.item_code].append(item)

# final_dict = dict(final_item)

# grouped = defaultdict(list)
# for item in doc.items:
#     if "fabric" in item.item_name.lower():
#         grouped[item.item_code].append(item)

# grouped_dict = dict(grouped)

# for items in final_dict:
#     for row in final_dict[items]:
#         for item in doc.items:
#             if item.idx == row.idx:
#                 for it in grouped_dict:
#                         for j in grouped_dict[it]:
#                             new_row = doc.append("items",{})
#                             for key in row.as_dict():
#                                 if key not in ["name","idx","qty","custom_sub_batch"]:
#                                     new_row.set(key,row.get(key))
#                             new_row.set("qty",j.qty)
#                             new_row.set("custom_sub_batch",j.custom_sub_batch if j.custom_sub_batch else "")


# CHECK WHETHER BATCH ALREADY EXISTS BEFORE SUBMITTING
def check_before_submit(doc, method=None):
    for item in doc.items:
        if item.custom_sub_batch and item.is_finished_item:
            if frappe.db.exists(
                "Batch",
                {"custom_sub_batch": item.custom_sub_batch, "item": item.item_code},
            ):
                frappe.throw(
                    msg=f"The Sub batch {item.custom_sub_batch} already exsists for {item.item_code}"
                )


@frappe.whitelist()
def qty_in_quick_entry(docname, method=None):
    doc = frappe.get_doc("Stock Entry", docname)
    batch_obj = {}
    for item in doc.custom_quick_entry:
        if item.item and item.sub_batch and item.qty == 0:
            batches = frappe.db.get_all(
                "Batch",
                {"custom_sub_batch": item.sub_batch, "item": item.item},
                pluck="batch_qty",
            )
            for batch in batches:
                if item.item not in batch_obj:
                    batch_obj[item.item] = []
                batch_obj[item.item].append(
                    [
                        item.sub_batch,
                        batch,
                        item.source_warehouse or "",
                        item.target_warehouse or "",
                    ]
                )
    if batch_obj:
        doc.custom_quick_entry = []
        for key, val in batch_obj.items():
            for values in val:
                if key and values[0] and values[1] not in doc.custom_quick_entry:
                    doc.append(
                        "custom_quick_entry",
                        {
                            "item": key,
                            "source_warehouse": values[2],
                            "target_warehouse": values[3],
                            "sub_batch": values[0],
                            "qty": values[1],
                        },
                    )
        doc.save()
        # qty=0
        # batches = frappe.db.get_all("Batch",{"custom_sub_batch":item.sub_batch,"item":item.item},pluck="batch_qty")
        # for batch in batches:
        #     qty+=batch
        # item.qty = qty


# FUNCTIONALITY TO AUTO FETCH BATCHES ON FIFO BASIS IN STOCK ENTRY
@frappe.whitelist()
def show_batches(docname=None, method=None):
    doc = frappe.get_doc("Stock Entry", docname)
    to_remove = []
    wo = frappe.get_doc("Work Order",doc.work_order)
    is_seg = False
    for items in wo.operations:
        if(items.operation=="Segregation"):
            is_seg = True
            

    if doc.custom_quick_entry:
        original_entries = list(doc.custom_quick_entry)
        processed_batches = {}

        for entry in original_entries:
            if not entry.source_warehouse or not entry.item:
                continue
            
            processed_batches.setdefault(entry.item, [])
            existing_qty = sum(
                e.qty for e in doc.custom_quick_entry if e.item == entry.item
            )
            target_qty = sum(i.qty for i in doc.items if i.item_code == entry.item)

            if existing_qty >= target_qty:
                continue

            # Get batches directly ordered by creation date (FIFO)
            batches = frappe.db.sql(
                """
                SELECT 
                    sle.warehouse,
                    sbb_entry.batch_no,
                    b.creation as batch_date,
                    SUM(sle.actual_qty) as available_qty
                FROM `tabStock Ledger Entry` sle
                INNER JOIN `tabSerial and Batch Entry` sbb_entry 
                    ON sle.serial_and_batch_bundle = sbb_entry.parent
                INNER JOIN `tabBatch` b 
                    ON sbb_entry.batch_no = b.name
                WHERE sle.item_code = %s 
                    AND sle.warehouse = %s
                    AND sle.is_cancelled = 0
                GROUP BY sbb_entry.batch_no, sle.warehouse
                HAVING SUM(sle.actual_qty) > 0
                ORDER BY b.creation ASC
            """,
                (entry.item, entry.source_warehouse),
                as_dict=True,
            )

            for batch_item in batches:
                if existing_qty >= target_qty:
                    break

                if batch_item.batch_no in processed_batches[entry.item]:
                    continue

                batch_qty = get_batch_qty(batch_item.batch_no, entry.source_warehouse)

                if batch_qty <= 0:
                    continue

                batch_doc = frappe.get_doc("Batch", batch_item.batch_no)
                sub_batch_value = getattr(batch_doc, "custom_sub_batch", "")                

                if(is_seg):
                    alloc_qty = min(batch_qty, target_qty - existing_qty)
                
                if not is_seg:
                    alloc_qty = batch_qty

                if alloc_qty <= 0:
                    continue

                child = doc.append(
                    "custom_quick_entry",
                    {
                        "item": entry.item,
                        "sub_batch": sub_batch_value,
                        "source_warehouse": batch_item.warehouse,
                        "batch": batch_item.batch_no,
                        "qty": flt(alloc_qty),
                    },
                )

                processed_batches[entry.item].append(batch_item.batch_no)
                existing_qty += alloc_qty

            to_remove.append(entry.name)

        for name in set(to_remove):
            for row in doc.custom_quick_entry:
                if row.name == name:
                    doc.remove(row)

        doc.save()
        frappe.db.commit()
        return True


@frappe.whitelist()
def get_unconsumed_transfers(work_order,opn = None, current_stock_entry=None):
    # Added operation as opn too for job card
    """
    Get materials from Material Transfer entries that haven't been consumed yet
    by checking against completed Manufacture entries
    """

    # Get all Material Transfer for Manufacture entries for this work order
    transfers = frappe.db.sql(
        """
        SELECT 
            se.name,
            sei.item_code,
            sei.t_warehouse as warehouse,
            sei.batch_no,
            sei.qty,
            sei.custom_sub_batch as sub_batch
        FROM `tabStock Entry` se
        INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
        WHERE 
            se.work_order = %s
            AND se.stock_entry_type = 'Material Transfer for Manufacture'
            AND se.docstatus = 1
            AND sei.batch_no IS NOT NULL
            AND sei.batch_no != ''
        ORDER BY se.posting_date ASC, se.posting_time ASC
    """,
        work_order,
        as_dict=1,
    )

    if not transfers:
        return []

    # Get all consumed materials from Manufacture entries (excluding current one)
    consumed_query = """
        SELECT 
            sei.item_code,
            sei.s_warehouse as warehouse,
            sei.batch_no,
            SUM(sei.qty) as consumed_qty
        FROM `tabStock Entry` se
        INNER JOIN `tabStock Entry Detail` sei ON se.name = sei.parent
        WHERE 
            se.work_order = %s
            AND se.stock_entry_type = 'Manufacture'
            AND se.docstatus = 1
            AND sei.batch_no IS NOT NULL
            AND sei.batch_no != ''
    """

    params = [work_order]

    # Exclude current stock entry if it exists (for draft entries being updated)
    if current_stock_entry:
        consumed_query += " AND se.name != %s"
        params.append(current_stock_entry)

    consumed_query += """
        GROUP BY sei.item_code, sei.s_warehouse, sei.batch_no
    """

    consumed = frappe.db.sql(consumed_query, tuple(params), as_dict=1)

    # Create a lookup dict for consumed quantities
    consumed_dict = {}
    for c in consumed:
        key = (c.item_code, c.warehouse, c.batch_no)
        consumed_dict[key] = c.consumed_qty

    # Calculate available (unconsumed) quantities
    unconsumed = []
    batch_tracker = {}  # Track cumulative for same batch across multiple transfers

    for transfer in transfers:
        key = (transfer.item_code, transfer.warehouse, transfer.batch_no)

        # Get total transferred for this batch
        if key not in batch_tracker:
            batch_tracker[key] = {
                "transferred": 0,
                "item_code": transfer.item_code,
                "warehouse": transfer.warehouse,
                "batch_no": transfer.batch_no,
                "sub_batch": transfer.sub_batch,
            }

        batch_tracker[key]["transferred"] += transfer.qty

    # Calculate unconsumed for each unique batch
    for key, data in batch_tracker.items():
        consumed_qty = consumed_dict.get(key, 0)
        
        # MADE AN EXCEPTION FOR SEGREGATION
        if opn == "Segregation":
            available_qty = data['transferred'] - consumed_qty
        
        if opn != "Segregation":
            # using get_batch_qty function so now qty will always be right
            available_qty = get_batch_qty(
                data["batch_no"], data["warehouse"], data["item_code"]
            )

        if available_qty > 0:
            unconsumed.append(
                {
                    "item_code": data["item_code"],
                    "warehouse": data["warehouse"],
                    "batch_no": data["batch_no"],
                    "sub_batch": data["sub_batch"],
                    "available_qty": flt(available_qty, 5),
                    "transferred_qty": flt(data["transferred"], 5),
                    "consumed_qty": flt(consumed_qty, 5),
                }
            )

    # Sort by item and batch (oldest first for FIFO)
    unconsumed = sorted(unconsumed, key=lambda x: (x["item_code"], x["batch_no"]))

    return unconsumed


# giving the qty of the batch via sub batch
@frappe.whitelist()
def get_sub_batch_qty(item, sub_batch, warehouse):
    batch = frappe.db.get_all(
        "Batch",
        filters={"custom_sub_batch": sub_batch, "item": item},
        limit_page_length=1,
        pluck="name",
    )
    return [get_batch_qty(batch[0], warehouse, item), batch[0]]


@frappe.whitelist()
def custom_enter_as_bales(docname, method=None):
    doc = frappe.get_doc("Stock Entry", docname)
    """
    Button handler for custom_enter_as_bales
    Combines raw material batches to create finished goods with 9000 qty target
    Only works for Packaging operations
    """
    # Check if this is a Manufacturing entry with a Work Order
    if doc.stock_entry_type != "Manufacture" or not doc.work_order:
        frappe.msgprint(
            "This function only works for Manufacturing entries with Work Orders"
        )
        return

    # Check if the Work Order has Packaging operation
    wo = frappe.get_doc("Work Order", doc.work_order)
    has_packaging = any(
        "Packaging" in opn.operation for opn in wo.operations if wo.operations
    )

    if not has_packaging:
        frappe.msgprint("This function only works for Packaging operations")
        return

    TARGET_QTY = 9000

    # Get all raw materials with custom_sub_batch
    raw_materials = [
        item
        for item in doc.items
        if not item.is_finished_item and item.custom_sub_batch
    ]

    # Sort by idx to maintain order
    raw_materials.sort(key=lambda x: x.idx)

    if not raw_materials:
        frappe.msgprint("No raw materials with sub_batch found")
        return

    # Get all finished goods (don't filter by qty=0, just get all finished goods)
    finished_goods = [item for item in doc.items if item.is_finished_item]

    if not finished_goods:
        frappe.msgprint("No finished goods found")
        return

    # Store the template finished good for reference
    template_fg = finished_goods[0]

    # Remove all existing finished goods
    items_to_remove = [fg.idx for fg in finished_goods]
    for item in list(doc.items):
        if item.idx in items_to_remove:
            doc.remove(item)

    # Create combined batches from raw materials
    combined_batches = []
    current_batch_qty = 0
    current_batch_sub_batches = []
    current_batch_usage = []  # Track sub_batch and qty used

    i = 0
    while i < len(raw_materials):
        raw_material = raw_materials[i]
        remaining_qty = raw_material.qty
        sub_batch = (
            raw_material.custom_sub_batch if raw_material.custom_sub_batch else ""
        )

        while remaining_qty > 0:
            space_in_current = TARGET_QTY - current_batch_qty

            if space_in_current > 0:
                # Add to current batch
                take_qty = min(space_in_current, remaining_qty)
                current_batch_qty += take_qty
                remaining_qty -= take_qty

                # Track sub_batch usage with quantity
                if sub_batch:
                    current_batch_usage.append(f"{sub_batch}: {take_qty}")
                    if sub_batch not in current_batch_sub_batches:
                        current_batch_sub_batches.append(sub_batch)

                # If current batch reaches or exceeds 9000, save it
                if current_batch_qty >= TARGET_QTY:
                    combined_batches.append(
                        {
                            "qty": current_batch_qty,
                            "sub_batches": list(current_batch_sub_batches),
                            "usage": list(current_batch_usage),
                        }
                    )
                    current_batch_qty = 0
                    current_batch_sub_batches = []
                    current_batch_usage = []
            else:
                # This shouldn't happen, but handle it
                break

        i += 1

    # Handle remaining batch (if any and if it's significant)
    if current_batch_qty >= TARGET_QTY:
        combined_batches.append(
            {
                "qty": current_batch_qty,
                "sub_batches": current_batch_sub_batches,
                "usage": current_batch_usage,
            }
        )

    # Create finished good rows for each combined batch with qty=1 from the start
    for batch in combined_batches:
        new_row = doc.append("items", {})
        for key in template_fg.as_dict():
            if key not in [
                "name",
                "idx",
                "custom_sub_batch",
                "qty",
                "custom_segregated_item_qty",
                "custom_sub_batches_used",
            ]:
                new_row.set(key, template_fg.get(key))

        # Set qty to 1 immediately (represents 1 combined batch)
        new_row.set("qty", 1)
        # Set the actual combined quantity in custom_segregated_item_qty
        new_row.set("custom_segregated_item_qty", batch["qty"])
        # Set combined sub_batches
        new_row.set("custom_sub_batch", ", ".join(batch["sub_batches"]))
        # Set detailed usage information
        new_row.set("custom_sub_batches_used", ", ".join(batch["usage"]))
        new_row.set("is_finished_item", 1)

    # Save the document to persist changes
    doc.save()

    frappe.msgprint(
        f"Created {len(combined_batches)} finished good batch(es) from {len(raw_materials)} raw materials"
    )


def split_final_product(doc, method=None):
    if doc.stock_entry_type == "Manufacture" and doc.work_order:
        wo = frappe.get_doc("Work Order", doc.work_order if doc.work_order else "")

        # Check if any operation is NOT Slitting, Bag Manufacturing, Segregation, or Packaging
        op = any(
            "Slitting" not in opn.operation
            and "Bag Manufacturing" not in opn.operation
            and "Segregation" not in opn.operation
            and "Packaging" not in opn.operation
            for opn in wo.operations
            if wo.operations
        )

        # Check if Packaging operation exists
        has_packaging = any(
            "Packaging" in opn.operation for opn in wo.operations if wo.operations
        )
      

        if op:
            fabrics = [
                item
                for item in doc.items
                if "fabric" in item.item_name.lower() and not item.is_finished_item
            ]
            finished_goods = [
                item
                for item in doc.items
                if item.is_finished_item and not item.get("custom_split_from_fabric")
            ]

            to_remove = []

            if len(fabrics) > 1:
                for finished_item in finished_goods:
                    to_remove.append(finished_item.idx)
                    for fabric in fabrics:
                        new_row = doc.append("items", {})
                        for key in finished_item.as_dict():
                            if key not in ["name", "idx", "custom_sub_batch"]:
                                new_row.set(key, finished_item.get(key))
                                new_row.set(
                                    "qty",
                                    fabric.custom_machine_consumption_qty or fabric.qty,
                                )
                                new_row.set(
                                    "custom_sub_batch",
                                    (
                                        fabric.custom_sub_batch
                                        if fabric.custom_sub_batch
                                        else ""
                                    ),
                                )
                                new_row.set("custom_split_from_fabric", True)
            else:
                for finished_item in finished_goods:
                    to_remove.append(finished_item.idx)
                    for fabric in fabrics:
                        new_row = doc.append("items", {})
                        for key in finished_item.as_dict():
                            if key not in ["name", "idx", "custom_sub_batch"]:
                                new_row.set(key, finished_item.get(key))
                                new_row.set(
                                    "custom_sub_batch",
                                    (
                                        fabric.custom_sub_batch
                                        if fabric.custom_sub_batch
                                        else ""
                                    ),
                                )
                                new_row.set("custom_split_from_fabric", True)

            for item in doc.items:
                if item.idx in to_remove:
                    doc.remove(item)

            # NEW LOGIC: Handle Packaging operation with 9000 qty batching
            # Only run this if has_packaging is True
            if has_packaging:
                TARGET_QTY = 9000

                # Get fabric items with their quantities and sub_batches
                fabrics = [
                    item
                    for item in doc.items
                    if (
                        "main body" in item.item_name.lower()
                        or "bags" in item.item_group.lower()
                    )
                    and not item.is_finished_item
                ]
                fabrics.sort(key=lambda x: x.idx)  # Maintain order

                # Get finished goods template (we'll recreate them)
                finished_goods = [
                    item
                    for item in doc.items
                    if item.is_finished_item
                    and not item.get("custom_split_from_fabric")
                ]

                if fabrics and finished_goods:
                    # Store the template finished good
                    template_fg = finished_goods[0]

                    # Remove all existing finished goods
                    items_to_remove = [fg.idx for fg in finished_goods]
                    for item in doc.items:
                        if item.idx in items_to_remove:
                            doc.remove(item)

                    # Create combined batches
                    combined_batches = []
                    current_batch_qty = 0
                    current_batch_sub_batches = []
                    current_batch_usage = []  # Track sub_batch and qty used

                    for fabric in fabrics:
                        remaining_fabric_qty = fabric.qty
                        fabric_sub_batch = (
                            fabric.custom_sub_batch if fabric.custom_sub_batch else ""
                        )

                        while remaining_fabric_qty > 0:
                            space_in_current = TARGET_QTY - current_batch_qty

                            if space_in_current > 0:
                                # Add to current batch
                                take_qty = min(space_in_current, remaining_fabric_qty)
                                current_batch_qty += take_qty
                                remaining_fabric_qty -= take_qty

                                # Track sub_batch usage with quantity
                                if fabric_sub_batch:
                                    current_batch_usage.append(
                                        f"{fabric_sub_batch}: {take_qty}"
                                    )
                                    if (
                                        fabric_sub_batch
                                        not in current_batch_sub_batches
                                    ):
                                        current_batch_sub_batches.append(
                                            fabric_sub_batch
                                        )

                                # If current batch reaches 9000, save it
                                if current_batch_qty >= TARGET_QTY:
                                    combined_batches.append(
                                        {
                                            "qty": current_batch_qty,
                                            "sub_batches": list(
                                                current_batch_sub_batches
                                            ),
                                            "usage": list(current_batch_usage),
                                        }
                                    )
                                    current_batch_qty = 0
                                    current_batch_sub_batches = []
                                    current_batch_usage = []
                            else:
                                # Current batch is full, start new batch
                                combined_batches.append(
                                    {
                                        "qty": current_batch_qty,
                                        "sub_batches": list(current_batch_sub_batches),
                                        "usage": list(current_batch_usage),
                                    }
                                )
                                current_batch_qty = 0
                                current_batch_sub_batches = []
                                current_batch_usage = []

                    # Handle remaining batch (if less than 9000, remove it)
                    if current_batch_qty >= TARGET_QTY:
                        combined_batches.append(
                            {
                                "qty": current_batch_qty,
                                "sub_batches": current_batch_sub_batches,
                                "usage": current_batch_usage,
                            }
                        )
                    # If current_batch_qty < TARGET_QTY, we discard it (as per requirement)

                    # Create finished good rows for each combined batch
                    for batch in combined_batches:
                        new_row = doc.append("items", {})
                        for key in template_fg.as_dict():
                            if key not in [
                                "name",
                                "idx",
                                "custom_sub_batch",
                                "qty",
                                "custom_segregated_item_qty",
                                "custom_sub_batches_used",
                            ]:
                                new_row.set(key, template_fg.get(key))

                        # Set qty to 1 (represents 1 combined batch)
                        new_row.set("qty", 1)
                        # Set the actual combined quantity in custom_segregated_item_qty
                        new_row.set("custom_segregated_item_qty", batch["qty"])
                        # Set combined sub_batches
                        new_row.set("custom_sub_batch", ", ".join(batch["sub_batches"]))
                        # Set detailed usage information
                        new_row.set(
                            "custom_sub_batches_used", ", ".join(batch["usage"])
                        )
                        new_row.set("custom_split_from_fabric", True)

        if not op:
            # Check if Packaging operation exists
             # NEW LOGIC: Handle Packaging operation with bale-based batching

            has_packaging = any(
                "Packaging" in opn.operation for opn in wo.operations if wo.operations
            )
            
            
            if has_packaging:
                # Get fabric items with their quantities and sub_batches
                fabrics = [
                    item
                    for item in doc.items
                    if (
                        "main body" in item.item_name.lower()
                        or "bags" in item.item_group.lower()
                    )
                    and not item.is_finished_item
                ]

                # Get finished goods template (we'll recreate them)
                finished_goods = [
                    item
                    for item in doc.items
                    if item.is_finished_item
                    and not item.get("custom_split_from_fabric")
                ]

                if fabrics and finished_goods:
                    # Store the template finished good
                    template_fg = finished_goods[0]

                    # Remove all existing finished goods
                    items_to_remove = [fg.idx for fg in finished_goods]
                    for item in doc.items:
                        if item.idx in items_to_remove:
                            doc.remove(item)

                    # Get custom_quick_entry data grouped by bale
                    bale_groups = {}

                    if doc.get("custom_quick_entry"):
                        for entry in doc.custom_quick_entry:
                            bale_number = entry.get("bale")
                            if bale_number:
                                if bale_number not in bale_groups:
                                    bale_groups[bale_number] = {
                                        "qty": 0,
                                        "sub_batches": [],
                                        "usage": []
                                    }

                                entry_qty = entry.get("qty") or 0
                                bale_groups[bale_number]["qty"] += entry_qty

                                # Track sub_batch if available
                                sub_batch = entry.get("sub_batch") or entry.get("custom_sub_batch")
                                if sub_batch:
                                    if sub_batch not in bale_groups[bale_number]["sub_batches"]:
                                        bale_groups[bale_number]["sub_batches"].append(sub_batch)
                                    bale_groups[bale_number]["usage"].append(f"{sub_batch}: {entry_qty}")

                    # Create finished good rows for each bale group
                    for bale_number in sorted(bale_groups.keys()):
                        bale_data = bale_groups[bale_number]

                        new_row = doc.append("items", {})
                        for key in template_fg.as_dict():
                            if key not in [
                                "name",
                                "idx",
                                "custom_sub_batch",
                                "qty",
                                "custom_segregated_item_qty",
                                "custom_sub_batches_used",
                            ]:
                                new_row.set(key, template_fg.get(key))

                        # Set qty to the total quantity for this bale
                        new_row.set("qty", bale_data["qty"])
                        # Set the actual combined quantity in custom_segregated_item_qty
                        new_row.set("custom_segregated_item_qty", bale_data["qty"])
                        # Set combined sub_batches
                        new_row.set("custom_sub_batch", ", ".join(bale_data["sub_batches"]))
                        # Set detailed usage information
                        new_row.set("custom_sub_batches_used", ", ".join(bale_data["usage"]))
                        new_row.set("custom_split_from_fabric", True)


            fabrics = [
                item
                for item in doc.items
                if (
                    "main body" in item.item_name.lower()
                    or "bags" in item.item_group.lower()
                )
                and not item.is_finished_item
            ]
            fabric_sum = sum(
                item.qty
                for item in doc.items
                if (
                    "main body" in item.item_name.lower()
                    or "bags" in item.item_group.lower()
                )
                and not item.is_finished_item
            )
            finished_goods = [
                item
                for item in doc.items
                if item.is_finished_item
                and "slit" not in item.item_name.lower()
                and not item.get("custom_split_from_fabric")
            ]

            # Skip if no finished goods items found
            if not finished_goods:
                return

            # target_quantity = frappe.get_value("Item", finished_goods[0].item_code, "custom_bale_qty") or 9000

            to_remove = []

            if len(fabrics) > 1:
                for finished_item in finished_goods:
                    to_remove.append(finished_item.idx)
                    for fabric in fabrics:
                        fabric_perc = (fabric.qty / fabric_sum) * 100
                        new_row = doc.append("items", {})
                        for key in finished_item.as_dict():
                            if key not in ["name", "idx", "custom_sub_batch","qty"]:
                                new_row.set(key, finished_item.get(key))
                                new_row.set(
                                    "custom_manufactured_good_qty",
                                (fabric.custom_manufactured_good_qty)
                                )
                                new_row.set(
                                    "qty",
                                    # Manufactured qty for AD*STAR finished goods,, custom machine consumption qty for getting consumption per batch
                                    int(fabric.custom_manufactured_good_qty or fabric.custom_machine_consumption_qty or fabric.qty),
                                )
                                
                                new_row.set(
                                    "custom_sub_batch",
                                    (
                                        fabric.custom_sub_batch
                                        if fabric.custom_sub_batch
                                        else ""
                                    ),
                                )
                                new_row.set("custom_split_from_fabric", True)
            else:
                for finished_item in finished_goods:
                    item = frappe.get_doc("Item", finished_item.item_code)
                    if (
                        item.has_batch_no
                        and "pkg" not in finished_item.item_name.lower()
                        and "fg" not in finished_item.item_name.lower()
                    ):
                        to_remove.append(finished_item.idx)
                        for fabric in fabrics:
                            new_row = doc.append("items", {})
                            for key in finished_item.as_dict():
                                if key not in ["name", "idx", "custom_sub_batch"]:
                                    new_row.set(key, finished_item.get(key))
                                    new_row.set(
                                        "custom_sub_batch",
                                        (
                                            fabric.custom_sub_batch
                                            if fabric.custom_sub_batch
                                            else ""
                                        ),
                                    )
                                    new_row.set("custom_split_from_fabric", True)

            for item in doc.items:
                if item.idx in to_remove:
                    doc.remove(item)

            
            
@frappe.whitelist()
def set_enter_as_bales(docname):
    doc = frappe.get_doc("Stock Entry", docname)
    wo = frappe.get_doc("Work Order", doc.work_order)
    pkg = any("Packaging" in opn.operation for opn in wo.operations)

    if pkg:
        return True
    else:
        return False


@frappe.whitelist()
def set_serial_number_after_submit(docname, method=None):
    SEND_FOR_SPARE_STATUS = "Sent For Repair"
    AVAILABLE_SPARE_STATUS = "Available"
    repairable_spares_group = "Repairable Spares"
    workstation_spare_doctype_name = "Workstation Spare Parts"
    spare_history_doctype_name = "Spares Move History"

    doc = frappe.get_doc("Stock Entry", docname)
    asset_name = frappe.db.get_value('Asset Repair', doc.asset_repair, 'asset')

    # ##print('======== -----doc ----========',doc)
    if doc.custom_stock_entry_reference == "Workstation Spare Parts":
        spare_move_history_list = frappe.db.get_list(
            "Spares Move History",
            filters={"stock_entry_reference": doc.name},
            fields=["name", "spare_entry_reference", "current_status"],
        )
        # #print("===================here is the spare move history list ======",spare_move_history_list)
        for history in spare_move_history_list:
            history_doc = frappe.get_doc("Spares Move History", history.name)
            history_doc.stock_entry_submission_date = today()
            history_doc.is_stock_entry_submitted = True
            history_doc.save(ignore_permissions=True)
            #print('============here isths history ==',history.spare_entry_reference)
            spare_entry_doc = frappe.get_doc("Workstation Spare Parts",history.spare_entry_reference)
            spare_entry_doc.spare_status = "In Use" if history.current_status == "Temporarily Consumed" else history.current_status
            if spare_entry_doc.item_serial_number:
                            f_serial_doc = frappe.get_doc('Serial No',spare_entry_doc.item_serial_number)
                            f_serial_doc.status = "Inactive"
                            f_serial_doc.save(ignore_permissions = True)
            spare_entry_doc.save(ignore_permissions=True)
            #print("===================spare_entry_doc.spare_status -===",spare_entry_doc.spare_status )
        try:
            if doc.stock_entry_type == "Spares Consumption" and spare_entry_doc.spare_status == "In Use" :
                repairable_items_for_recovery = []
                #print('============================ repairable_items_for_recovery == ',repairable_items_for_recovery)
                for item in doc.items:
                    if item.item_group == repairable_spares_group and item.custom_stock_item_move_reference:
                        #print('======================= if == if item.item_group == repairable_spares_group and item.custom_stock_item_move_reference:== ')
                        spare_doc = frappe.get_doc(
                            workstation_spare_doctype_name,
                            item.custom_stock_item_move_reference
                        )
                        if not item.serial_no:
                            batch_bundle_doc = frappe.get_doc("Serial and Batch Bundle",item.serial_and_batch_bundle)
                            for serial in batch_bundle_doc.entries:
                                # ##print('========iffffffffffff=======it workeddd!!!============',serial.serial_no)
                                spare_doc.item_serial_number = serial.serial_no
                            
                        else:
                            spare_doc.item_serial_number = item.serial_no 
                        if spare_doc.item_serial_number:
                            serial_doc = frappe.get_doc('Serial No',spare_doc.item_serial_number)
                            serial_doc.status = "Inactive"
                            serial_doc.save(ignore_permissions = True)
                        # #print('before =99999999999999999999999999999999================ item t warehosue ===', item.t_warehouse)
                        # item.t_warehouse = spare_doc.target_warehouse
                        # #print('afeter=99999999999999999999999999999999================ item t warehosue ===', item.t_warehouse)
                        # spare_doc.source_warehouse = spare_doc.target_warehouse
                        # #print('afeter=888888888888888888888888888================ spare_doc.source_warehouse ===', spare_doc.source_warehouse)
                        
                        if not spare_doc:
                            frappe.throw(f"Workstation Spare Parts {item.custom_stock_item_move_reference} not found, It might be deleted.")
                        # HARD STOP
                        # if item.serial_no and spare_doc.item_serial_number != item.serial_no:
                        #     frappe.throw(
                        #         _(
                        #             'The serial number you have choosed is different from the existing spare history, '
                        #             'Please recheck and put the same serial number here.'
                        #         )
                        #     )
                        if spare_doc and ( spare_doc.spare_status == "In Use"  ):
                            # Deep copy item to avoid modifying original
                            item_copy = frappe.copy_doc(item)
                            item_copy.t_warehouse = spare_doc.target_warehouse
                            item_copy.s_warehouse = spare_doc.target_warehouse
                            manual_to_warehouse = spare_doc.target_warehouse
                            repairable_items_for_recovery.append({
                                'item': item_copy,  # original ki jagah copy use kar
                                'spare_doc': spare_doc
                            })
                            # try:
                            #     if item.serial_and_batch_bundle:
                            #         serial_doc = frappe.get_doc(
                            #             "Serial and Batch Bundle",
                            #             item.serial_and_batch_bundle
                            #         )

                            #     spare_history_doc = frappe.get_doc({
                            #         "doctype": spare_history_doctype_name,
                            #         "stock_entry_reference": doc.name,
                            #         "spare_entry_reference": spare_doc.name if spare_doc else "",
                            #         "workstation": item.custom_workstation,
                            #         "entry_date": doc.posting_date,
                            #         "spare_part": item.item_code,
                            #         "item_serial_number": spare_doc.item_serial_number,
                            #         "old_status": "Installation Pending",
                            #         "current_status": "Temporarily Consumed",
                            #         "from_warehouse": item.s_warehouse,
                            #         "to_warehouse": item.t_warehouse,
                            #         "is_stock_entry_submitted": True,
                            #         "stock_entry_submission_date": today(),
                            #         "details": f"Consumed from stock entry {doc.name}",
                            #         "asset_repair_reference": doc.asset_repair,
                            #         "asset_reference": asset_name,
                            #     })
                            #     spare_history_doc.insert(ignore_permissions=True)
                            #     spare_history_doc.save(ignore_permissions=True)

                            # except Exception:
                            #     frappe.log_error(
                            #         "Workstation Spare Entry Creation Error",
                            #         frappe.get_traceback()
                            #     )
                            #     frappe.throw(
                            #         _("Error updating spare status: {0}").format(
                            #             frappe.get_traceback()
                            #         )
                            #     )

                            # doc.save(ignore_permissions=True)
                # #print('=============out for lop =============== repairable_items_for_recovery == ',repairable_items_for_recovery)

                # Recovery creation
                if repairable_items_for_recovery and doc.stock_entry_type == "Spares Consumption":
                    # #print('============if repairable_items_for_recovery =============== repairable_items_for_recovery == ',repairable_items_for_recovery)

                    try:
                        recovery_entry_name = create_spare_recovery_entry(
                            doc,
                            repairable_items_for_recovery,
                            asset_name,
                            workstation_spare_doctype_name,
                            spare_history_doctype_name,
                            manual_to_warehouse
                        )

                        if recovery_entry_name:
                            frappe.msgprint(
                                _("Spare Recovery entry {0} created successfully").format(
                                    recovery_entry_name
                                ),
                                alert=True,
                                indicator='green'
                            )

                    except Exception as e:
                        frappe.log_error(
                            "Spare Recovery Creation Error",
                            frappe.get_traceback()
                        )
                        # Framework will rollback on throw
                        frappe.throw(
                            _("Failed to create Spare Recovery entry: {0}").format(str(e))
                        )

        except Exception as e:
            # Ensure exception bubbles up so submit is cancelled
            raise e

        frappe.db.commit()
            # for h in history:
            #     ##print('====here is the H======',h)
            #     ##print('====here is the H.spare_entry_reference======',h.spare_entry_reference)
        # ##print("=====================================",doc.name)
        for item in doc.items:
            # ##print(doc.)
            # ##print("=======================================",item)
            # ##print('===============it0980909809808!!============',item.serial_no)
            # if item.custom_stock_item_move_reference:
            #     spare_doc = frappe.get_doc("Workstation Spare Parts",item.custom_stock_item_move_reference)
            #     if item.serial_and_batch_bundle and spare_doc.spare_status == AVAILABLE_SPARE_STATUS and spare_doc.item_serial_number:
            #         #print ('============ent ered in if item.serial_and_batch_bundle and spare_doc.spare_status == AVAILABLE_SPARE_STATUS == ',spare_doc.spare_status)
            #         serial_doc = frappe.get_doc("Serial No",spare_doc.item_serial_number)
            #         serial_doc.status = "Inactive"
            #         serial_doc.save()
            #         frappe.db.commit()
            #     if item.serial_and_batch_bundle and spare_doc.spare_status != "Consumed" and spare_doc.item_serial_number:
            #         #print ('============ent ered in else --- item.serial_and_batch_bundle and spare_doc.spare_status == Consumed == ',spare_doc.spare_status)
            #         serial_doc = frappe.get_doc("Serial No",spare_doc.item_serial_number)
            #         if serial_doc.status == "Inactive":
            #             #print ('============entered in if --- serial_doc.status == "Inactive"== ',spare_doc.spare_status)
            #             serial_doc.status == "Active"
            #             serial_doc.save()
            #             frappe.db.commit()
            if item.custom_stock_item_move_reference:
                spare_doc = frappe.get_doc(
                    "Workstation Spare Parts", item.custom_stock_item_move_reference
                )

                # #print('========iffffffffffff=======it workeddd!!!============',item.serial_and_batch_bundle)
                if (
                    item.serial_and_batch_bundle
                    and spare_doc.spare_status == "Installation Pending"
                ):
                    serial_doc = frappe.get_doc(
                        "Serial and Batch Bundle", item.serial_and_batch_bundle
                    )
                    for serial in serial_doc.entries:
                        # ##print('========iffffffffffff=======it workeddd!!!============',serial.serial_no)
                        spare_doc.item_serial_number = serial.serial_no
                        spare_doc.spare_status = "In Use"
                        spare_doc.save(ignore_permissions=True)
                        frappe.db.commit()
                        # frappe.set_value()
                elif not item.serial_and_batch_bundle:
                    frappe.throw(
                        f"Serial Number missing in Stock Entry for:\n\n"
                        f"• Row: {item.idx}\n"
                        f"• Item: {item.item_code}\n\n"
                        "This is a Repairable Spares Stock Entry. Please assign Serial Numbers "
                        "for all repairable items and resubmit this entry."
                    )
                elif spare_doc.spare_status != "Installation Pending":
                    # ##print('========elllliffffffffffff====!=Installation Pending==!============',spare_doc.spare_status)
                    break


@frappe.whitelist()
def create_workstation_spares_doc_entries(docname, method=None):
    repairable_spares_group = "Repairable Spares"
    workstation_spare_doctype_name = "Workstation Spare Parts"
    spare_history_doctype_name = "Spares Move History"

    doc = frappe.get_doc("Stock Entry", docname)
    asset_name = frappe.db.get_value('Asset Repair', doc.asset_repair, 'asset')
    if not asset_name:
        if not doc.custom_default_workstation:
            frappe.throw("Default Workstation is not set in this Stock Entry to fetch Asset.")
        asset_name = frappe.db.get_value('Workstation', doc.custom_default_workstation, 'custom_asset')
        #print('========asset_name from workstation =======',asset_name)
        if not asset_name:
            frappe.throw(f"Asset not found from Workstation {doc.custom_default_workstation} linked with this Stock Entry.")
        
    try:
        # ============================================
        # 1) SPARES TRANSFER
        # ============================================
        if doc.stock_entry_type == "Spares Transfer":
            for item in doc.items:
                if item.item_group == repairable_spares_group:
                    if item.serial_and_batch_bundle:
                        serial_doc = frappe.get_doc("Serial and Batch Bundle", item.serial_and_batch_bundle)
                        for serial in serial_doc.entries:
                            try:
                                spare_doc = frappe.get_doc({
                                    "doctype": workstation_spare_doctype_name,
                                    "workstation": item.custom_workstation,
                                    # "date_of_installation": doc.posting_date,
                                    "spare_part": item.item_code,
                                    "item_serial_number": serial.serial_no,
                                    "spare_status": "Installation Pending",
                                    "source_warehouse": item.s_warehouse,
                                    "target_warehouse": item.t_warehouse,
                                    "asset_reference": asset_name,
                                    "docstatus": 1
                                })
                                spare_doc.insert(ignore_permissions=True)
                                spare_doc.save()
                                item.custom_stock_item_move_reference = spare_doc.name

                            except Exception:
                                frappe.log_error(
                                    "Workstation Spare Entry Creation Error",
                                    frappe.get_traceback()
                                )
                                raise

                            try:
                                spare_history_doc = frappe.get_doc({
                                    "doctype": spare_history_doctype_name,
                                    "stock_entry_reference": doc.name,
                                    "spare_entry_reference": spare_doc.name if spare_doc else "",
                                    "workstation": item.custom_workstation,
                                    "entry_date": doc.posting_date,
                                    "spare_part": item.item_code,
                                    "item_serial_number": serial.serial_no,
                                    "current_status": "Installation Pending",
                                    "from_warehouse": item.s_warehouse,
                                    "to_warehouse": item.t_warehouse,
                                    "is_stock_entry_submitted": True,
                                    "stock_entry_submission_date": today(),
                                    "details": f"Created from stock entry.",
                                    "asset_repair_reference": doc.asset_repair,
                                    "asset_reference": asset_name,
                                })
                                spare_history_doc.insert()
                                spare_history_doc.save(ignore_permissions=True)
                                frappe.db.commit()
                                

                            except Exception:
                                frappe.log_error(
                                    "Workstation Spare Entry Creation Error",
                                    frappe.get_traceback()
                                )
                                frappe.throw(
                                    _("Error updating spare status: {0}").format(
                                        frappe.get_traceback()
                                    )
                                )

            doc.save(ignore_permissions=True)

        # ============================================
        # 2) SPARES CONSUMPTION
        # ============================================
        elif doc.stock_entry_type == "Spares Consumption" and doc.custom_stock_entry_reference != "Workstation Spare Parts":
            repairable_items_for_recovery = []

            for item in doc.items:
                if item.item_group == repairable_spares_group and item.custom_stock_item_move_reference:
                    spare_doc = frappe.get_doc(
                        workstation_spare_doctype_name,
                        item.custom_stock_item_move_reference
                    )
                    if not spare_doc:
                        frappe.throw(f"Workstation Spare Parts {item.custom_stock_item_move_reference} not found, It might be deleted.")
                    # HARD STOP
                    if item.serial_no and spare_doc.item_serial_number != item.serial_no:
                        frappe.throw(
                            _(
                                'The serial number you have choosed is different from the existing spare history, '
                                'Please recheck and put the same serial number here.'
                            )
                        )

                    if spare_doc and spare_doc.spare_status == "Installation Pending":
                        spare_doc.spare_status = "In Use"
                        repairable_items_for_recovery.append({
                            'item': item,
                            'spare_doc': spare_doc
                        })

                        try:
                            if item.serial_and_batch_bundle:
                                serial_doc = frappe.get_doc(
                                    "Serial and Batch Bundle",
                                    item.serial_and_batch_bundle
                                )

                            spare_history_doc = frappe.get_doc({
                                "doctype": spare_history_doctype_name,
                                "stock_entry_reference": doc.name,
                                "spare_entry_reference": spare_doc.name if spare_doc else "",
                                "workstation": item.custom_workstation,
                                "entry_date": doc.posting_date,
                                "spare_part": item.item_code,
                                "item_serial_number": spare_doc.item_serial_number,
                                "old_status": "Installation Pending",
                                "current_status": "Temporarily Consumed",
                                "from_warehouse": item.s_warehouse,
                                "to_warehouse": item.t_warehouse,
                                "is_stock_entry_submitted": True,
                                "stock_entry_submission_date": today(),
                                "details": f"Consumed from stock entry {doc.name}",
                                "asset_repair_reference": doc.asset_repair,
                                "asset_reference": asset_name,
                            })
                            spare_history_doc.insert(ignore_permissions=True)
                            spare_history_doc.save(ignore_permissions=True)

                        except Exception:
                            frappe.log_error(
                                "Workstation Spare Entry Creation Error",
                                frappe.get_traceback()
                            )
                            frappe.throw(
                                _("Error updating spare status: {0}").format(
                                    frappe.get_traceback()
                                )
                            )

                        doc.save(ignore_permissions=True)

            # Recovery creation
            if repairable_items_for_recovery:
                try:
                    recovery_entry_name = create_spare_recovery_entry(
                        doc,
                        repairable_items_for_recovery,
                        asset_name,
                        workstation_spare_doctype_name,
                        spare_history_doctype_name,
                    )

                    if recovery_entry_name:
                        frappe.msgprint(
                            _("Spare Recovery entry {0} created successfully").format(
                                recovery_entry_name
                            ),
                            alert=True,
                            indicator="green",
                        )

                except Exception as e:
                    frappe.log_error(
                        "Spare Recovery Creation Error",
                        frappe.get_traceback()
                    )
                    # Framework will rollback on throw
                    frappe.throw(
                        _("Failed to create Spare Recovery entry: {0}").format(str(e))
                    )

    except Exception as e:
        # Ensure exception bubbles up so submit is cancelled
        raise e

def create_spare_recovery_entry(
    doc,
    repairable_items,
    asset_name,
    workstation_spare_doctype_name,
    spare_history_doctype_name,
    manual_to_warehouse=None
):
    """
    Create Spare Recovery stock entry for consumed repairable spares
    """
    try:
        # Create new Stock Entry for recovery
        recovery_entry = frappe.get_doc({
            "doctype": "Stock Entry",
            "custom_stock_entry_reference": doc.name,
            "set_posting_time":True,
            "stock_entry_type": "Spares Recovery",
            "posting_date": doc.posting_date,
            "posting_time": doc.posting_time,
            "asset_repair": doc.asset_repair,
            "custom_default_workstation": doc.custom_default_workstation,
            "company": doc.company,
            "from_warehouse": None,              # No source for recovery
            "to_warehouse": manual_to_warehouse if manual_to_warehouse else doc.from_warehouse,  # Return to original warehouse
            "items": [],
        })

        # Add items to recovery entry
        for item_data in repairable_items:
            item = item_data['item']
            spare_doc = item_data['spare_doc']

            # Get serial numbers
            serial_numbers = []
            if item.serial_and_batch_bundle:
                serial_bundle = frappe.get_doc(
                    "Serial and Batch Bundle", item.serial_and_batch_bundle
                )
                serial_numbers = [s.serial_no for s in serial_bundle.entries]

            recovery_entry.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": item.qty,
                "uom": item.uom,
                "basic_rate": 0,
                "basic_amount": 0,
                "additional_cost": 0,
                "valuation_rate": 0,
                "allow_zero_valuation_rate": True,
                "amount": 0,
                "conversion_factor": item.conversion_factor or 1,
                "transfer_qty": item.transfer_qty or item.qty,
                "s_warehouse": None,              # No source warehouse for recovery
                "t_warehouse": item.s_warehouse,  # Target is original source
                "serial_no": "\n".join(serial_numbers) if serial_numbers else None,
                "custom_select_serial_no": item.custom_select_serial_no,
                "custom_workstation": item.custom_workstation,
                "item_group": item.item_group,
                "custom_stock_item_move_reference": item.custom_stock_item_move_reference
            })
        # Insert + submit recovery entry
        recovery_entry.insert(ignore_permissions=True)
        old_status = "Temporarily Consumed"
        recovery_entry.submit()

        # Update spare docs + history
        for item_data in repairable_items:
            item = item_data['item']
            spare_doc = item_data['spare_doc']

            try:
                spare_doc.spare_status = "In Use"
                spare_doc.date_of_installation = doc.posting_date
                # spare_doc.target_warehouse = doc.from_warehouse
                spare_doc.save(ignore_permissions=True)
                if spare_doc.item_serial_number:
                            serial_doc = frappe.get_doc('Serial No',spare_doc.item_serial_number)
                            serial_doc.status = "Inactive"
                            serial_doc.save(ignore_permissions = True)
                # #print('=============== item.t_warehouse. == ',item.t_warehouse )
                recovery_history = frappe.get_doc({
                    "doctype": spare_history_doctype_name,
                    "stock_entry_reference": recovery_entry.name,
                    "spare_entry_reference": spare_doc.name,
                    "workstation": item.custom_workstation,
                    "entry_date": doc.posting_date,
                    "spare_part": item.item_code,
                    "item_serial_number": spare_doc.item_serial_number,
                    "old_status": old_status,
                    "current_status": "In Use",
                    "from_warehouse": None,
                    "to_warehouse": item.s_warehouse if item.s_warehouse else item.t_warehouse,
                    "is_stock_entry_submitted": True,
                    "stock_entry_submission_date": today(),
                    "entry_details": f"Recovered from consumption entry {doc.name}",
                    "asset_repair_reference": doc.asset_repair,
                    "asset_reference": asset_name,
                })
                recovery_history.insert(ignore_permissions=True)
                recovery_history.save(ignore_permissions=True)

            except Exception:
                frappe.log_error(
                    "Recovery History Creation Error",
                    frappe.get_traceback()
                )

        return recovery_entry.name

    except Exception:
        frappe.log_error(
            "Spare Recovery Entry Creation Failed",
            frappe.get_traceback()
        )
        # Let caller handle rollback via throw
        raise

@frappe.whitelist()
def seperate_repairable_spares_quantities(doc, method=None):

    repairable_spares_group = "Repairable Spares"
    new_items_list = []
    split_summary = []   
    if doc.stock_entry_type == "Spares Transfer" or doc.stock_entry_type == "Spares Consumption":

        for item in doc.items:

            if item.item_group == repairable_spares_group and item.qty > 1:
                original_qty = int(item.qty)
                split_summary.append(
                    f"{item.item_code} → Qty {original_qty} split into {original_qty} rows"
                )

                item.qty = 1
                new_items_list.append(item)

                for i in range(original_qty - 1):
                    new_row = frappe.new_doc(item.doctype)

                    for field in item.meta.fields:
                        if field.fieldtype not in ["Table", "Table MultiSelect"]:
                            setattr(
                                new_row,
                                field.fieldname,
                                getattr(item, field.fieldname, None),
                            )

                    new_row.qty = 1
                    new_row.idx = None
                    new_items_list.append(new_row)

            else:
                new_items_list.append(item)

        doc.items = []

        for idx, item in enumerate(new_items_list, start=1):
            item.idx = idx
            doc.append("items", item)

        if split_summary:
            msg = "<br>".join(split_summary)
            frappe.msgprint(
                f"""
                <b>Repairable Spare Quantities Adjusted</b><br><br>
                The following items had quantity > 1 and were split into individual rows:<br><br>
                {msg}
                <br><br>Each repairable spare row now has Qty = 1.
                """,
                indicator="blue",
                title="Rows Updated",
            )

def on_submit_update_maintenance_log_spares_status(doc, method=None):
    """
    On Stock Entry Submit, update spares flags in Asset Maintenance Log
    """
    if doc.custom_another_stock_entry_reference:
        update_maintenance_log_spares_status(doc.custom_another_stock_entry_reference)
        
        
def on_cancel_update_maintenance_log_spares_status(doc, method=None):
    """
    On Stock Entry Cancel, update spares flags in Asset Maintenance Log
    """
    if doc.custom_another_stock_entry_reference:
        update_maintenance_log_spares_status(doc.custom_another_stock_entry_reference)

def update_maintenance_log_spares_status(maintenance_log_name):
    """
    Update spares flags in Asset Maintenance Log based on Stock Entries
    """
    if not frappe.db.exists("Asset Maintenance Log", maintenance_log_name):
        return
    
    # Count stock entries by type
    stock_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "custom_another_stock_entry_reference": maintenance_log_name,
            "docstatus": 1
        },
        fields=["stock_entry_type"]
    )
    
    has_transfer = any(se.stock_entry_type == "Spares Transfer" for se in stock_entries)
    has_consumption = any(se.stock_entry_type == "Spares Consumption" for se in stock_entries)
    has_return = any(se.stock_entry_type == "Material Transfer" for se in stock_entries)
    
    # Update maintenance log
    frappe.db.set_value(
        "Asset Maintenance Log",
        maintenance_log_name,
        {
            "custom_spares_transferred": 1 if has_transfer else 0,
            "custom_spares_consumed": 1 if has_consumption else 0,
            "custom_spares_returned": 1 if has_return else 0
        },
        update_modified=False
    )

            # #print(f'============== Added item at position {idx} ==')
# @frappe.whitelist()
# def seperate_repairable_spares_quantities(doc, method=None):
#     # doc = frappe.get_doc("Stock Entry",docname)
#     #print('============== doc cc ==', doc.name)
#     #print('============== doc stock_entry_type ==', doc.stock_entry_type)
    
#     repairable_spares_group = "Repairable Spares"
#     #print('=============seperate_repairable_spares_quantities chal gya ====')
#     if doc.stock_entry_type == "Spares Transfer":
#             items_to_add = []
#             #print('=======2222222222222222222222======seperate_repairable_spares_quantities chal gya ====')
            
#             for item in doc.items:
#                 #print('=======44444444444444444444 fororrr====== chal gya ====')
                
#                 if item.item_group == repairable_spares_group and item.qty > 1:
#                     #print('=======555555555555555555555 fororrr====iffffff== chal gya ====')
                    
#                     target_line_qty = item.qty
#                     #print(" ==== here is the target line tqty ===",target_line_qty)
#                     item.qty = 1
#                     # item.idx = None
#                     for i in range(int(target_line_qty)-1):
#                         new_item = frappe.copy_doc(item)
#                         new_item.qty = 1
#                         items_to_add.append(new_item)
#                         # new_row.idx = None
#                         #print('============== -- line ==',i)
#                     # #print('============== -- line ==',item)
#             for item in items_to_add:
#                 #print('============== -- line ==',item)
#                 doc.append('items',item)


def submit_bales_on_stock_entry_submit(stock_entry_doc, method=None):
    """
    When a Material Issue Stock Entry is submitted, submit ALL linked Bales
    and set their status to 'Packed In House'.

    The Stock Entry references Bales Creator via custom_bales_creator field.
    All Bales linked to that Bales Creator are submitted.

    Alternative: Uses custom_bale_reference (comma-separated Bales names)
    if custom_bales_creator is not set.
    """
    # Only process Material Issue Stock Entries
    if stock_entry_doc.stock_entry_type != "Material Issue":
        return

    # Get linked Bales - either via Bales Creator or direct reference
    bales_to_submit = []

    # Method 1: Via Bales Creator reference
    bales_creator = getattr(stock_entry_doc, 'custom_bales_creator', None)
    if bales_creator:
        bales_to_submit = frappe.db.get_all(
            "Bales",
            filters={
                "source_document_type": "Bales Creator",
                "source_document": bales_creator,
                "docstatus": 0  # Only draft bales
            },
            pluck="name"
        )

    # Method 2: Via comma-separated Bales reference (fallback)
    # Skip if it looks like a Re-Bale reference (contains "Re-Bale:")
    if not bales_to_submit:
        bale_ref = getattr(stock_entry_doc, 'custom_bale_reference', None)
        if bale_ref and "Re-Bale:" not in bale_ref:
            bales_to_submit = [
                b.strip() for b in bale_ref.split(",") if b.strip()
            ]

    # Method 3: Via material_consumption_entry (for Re-Bale created Stock Entries)
    if not bales_to_submit:
        bales_to_submit = frappe.db.get_all(
            "Bales",
            filters={
                "material_consumption_entry": stock_entry_doc.name,
                "docstatus": 0  # Only draft bales
            },
            pluck="name"
        )

    if not bales_to_submit:
        return

    submitted_bales = []
    errors = []

    for bales_name in bales_to_submit:
        try:
            bales_doc = frappe.get_doc("Bales", bales_name)

            # Only submit if Bales is in Draft state
            if bales_doc.docstatus == 0:
                # Submit the Bales document
                # This triggers create_bales_ledger_entries in Bales.on_submit
                bales_doc.submit()

                # Set status to 'Packed In House' after submission
                frappe.db.set_value(
                    "Bales", bales_name,
                    "bales_status", "Packed In House",
                    update_modified=False
                )

                submitted_bales.append(bales_name)

        except Exception as e:
            errors.append(f"{bales_name}: {str(e)}")
            frappe.log_error(
                f"Error submitting Bales {bales_name}: {str(e)}",
                "Bales Submit Error"
            )

    if submitted_bales:
        frappe.msgprint(
            _("{0} Bales submitted and marked as Packed: {1}").format(
                len(submitted_bales), ", ".join(submitted_bales)
            ),
            indicator="green",
            alert=True,
        )

    if errors:
        frappe.throw(
            _("Failed to submit some Bales: {0}").format("<br>".join(errors))
        )


def _user_has_elevated_permission():
    """
    Check if current user has Administrator or System Manager role.
    These roles are allowed to cancel/delete Stock Entry with linked Bales.
    """
    user_roles = frappe.get_roles(frappe.session.user)
    return "Administrator" in user_roles or "System Manager" in user_roles


def _get_linked_bales(stock_entry_doc):
    """
    Get list of Bales linked to this Stock Entry.

    Checks multiple reference methods:
    1. custom_bales_creator - Link to Bales Creator (finds Bales via source_document)
    2. custom_bale_reference - Comma-separated list of Bales names
    3. Bales.material_consumption_entry - Reverse lookup (fallback)

    Returns list of Bales names (may be empty if no links found).
    """
    bales_list = []

    # Method 1: Via Bales Creator reference (custom field may not exist yet)
    try:
        bales_creator = getattr(stock_entry_doc, 'custom_bales_creator', None)
        if bales_creator:
            bales_list = frappe.db.get_all(
                "Bales",
                filters={
                    "source_document_type": "Bales Creator",
                    "source_document": bales_creator,
                    "docstatus": ["!=", 2]
                },
                pluck="name"
            )
    except Exception:
        # Field doesn't exist yet
        pass

    # Method 2: Via comma-separated Bales reference (custom field may not exist)
    if not bales_list:
        try:
            bale_ref = getattr(stock_entry_doc, 'custom_bale_reference', None)
            if bale_ref:
                bales_list = [
                    b.strip() for b in bale_ref.split(",") if b.strip()
                ]
        except Exception:
            pass

    # Method 3: Via Bales.material_consumption_entry reverse lookup (fallback)
    if not bales_list:
        bales_list = frappe.db.get_all(
            "Bales",
            filters={
                "material_consumption_entry": stock_entry_doc.name,
                "docstatus": ["!=", 2]
            },
            pluck="name"
        )

    return bales_list


def cancel_manufacture_bales(stock_entry_doc, method=None):
    """
    Cancel ALL linked Bales when Stock Entry is cancelled.

    Stock Entry is the SINGLE AUTHORITY for Bale lifecycle.
    This is the ONLY place where Bales cancellation is initiated.

    The Stock Entry may reference Bales via:
    1. custom_bales_creator (Link to Bales Creator)
    2. custom_bale_reference (comma-separated Bales names)

    Permission Handling:
    - Only Administrator / System Manager can cancel Stock Entry with linked Bales
    - Sets frappe.flags.stock_entry_bale_cancel = True to allow Bales.before_cancel
    - Flag is cleared immediately after cancel operation completes
    """
    # Only process Material Issue Stock Entries
    if stock_entry_doc.stock_entry_type != "Material Issue":
        return

    # Get linked Bales - either via Bales Creator or direct reference
    bales_to_cancel = _get_linked_bales(stock_entry_doc)

    if not bales_to_cancel:
        return

    # Verify user has elevated permissions
    if not _user_has_elevated_permission():
        frappe.throw(
            _(
                "Only Administrator or System Manager can cancel Stock Entry "
                "with linked Bales."
            )
        )

    # Check for dispatched bales first - block if any are dispatched
    dispatched_bales = []
    for bales_name in bales_to_cancel:
        status = frappe.db.get_value("Bales", bales_name, "bales_status")
        if status == "Dispatched":
            dispatched_bales.append(bales_name)

    if dispatched_bales:
        frappe.throw(
            _(
                "Cannot cancel Stock Entry. The following Bales have been dispatched: "
                "{0}. Please cancel the Delivery Note first."
            ).format(", ".join(dispatched_bales))
        )

    cancelled_bales = []
    deleted_bales = []
    errors = []

    # Set the STOCK ENTRY specific flag to allow Bales cancellation
    # This is the ONLY flag that Bales.before_cancel() checks
    frappe.flags.stock_entry_bale_cancel = True

    try:
        for bales_name in bales_to_cancel:
            try:
                bales_doc = frappe.get_doc("Bales", bales_name)

                # If draft (docstatus=0), delete with elevated permissions
                if bales_doc.docstatus == 0:
                    bales_doc.delete(ignore_permissions=True)
                    deleted_bales.append(bales_name)

                # If submitted (docstatus=1), cancel it
                elif bales_doc.docstatus == 1:
                    # Set ignore_links flag to bypass Bales Creator link check
                    bales_doc.flags.ignore_links = True
                    bales_doc.cancel()
                    cancelled_bales.append(bales_name)

            except frappe.DoesNotExistError:
                # Bales doesn't exist, skip
                pass
            except Exception as e:
                errors.append(f"{bales_name}: {str(e)}")
                # Use shorter title for error log (max 140 chars)
                frappe.log_error(
                    message=str(e),
                    title="Bales Cancel Error"
                )
    finally:
        # ALWAYS clear the flag immediately after operation
        frappe.flags.stock_entry_bale_cancel = False

    # Report results
    messages = []
    if cancelled_bales:
        messages.append(
            _("Cancelled {0} Bales: {1}").format(
                len(cancelled_bales), ", ".join(cancelled_bales)
            )
        )
    if deleted_bales:
        messages.append(
            _("Deleted {0} draft Bales: {1}").format(
                len(deleted_bales), ", ".join(deleted_bales)
            )
        )

    if messages:
        frappe.msgprint("<br>".join(messages), indicator="orange", alert=True)

    if errors:
        frappe.throw(
            _("Failed to cancel some Bales: {0}").format("<br>".join(errors))
        )


def delete_manufacture_bales(stock_entry_doc, method=None):
    """
    Delete ALL linked Bales when Stock Entry is deleted.

    The Stock Entry may reference Bales via:
    1. custom_bales_creator (Link to Bales Creator)
    2. custom_bale_reference (comma-separated Bales names)

    Permission Handling:
    - Only Administrator / System Manager can delete Stock Entry with linked Bales
    - Can only delete Draft or Cancelled Bales
    - Bales are deleted with elevated permissions (ignore_permissions=True)
    """
    # Only process Material Issue Stock Entries
    if stock_entry_doc.stock_entry_type != "Material Issue":
        return

    # Get linked Bales - either via Bales Creator or direct reference
    bales_to_delete = _get_linked_bales(stock_entry_doc)

    if not bales_to_delete:
        return

    # Verify user has elevated permissions
    if not _user_has_elevated_permission():
        frappe.throw(
            _(
                "Only Administrator or System Manager can delete Stock Entry "
                "with linked Bales."
            )
        )

    # Check for submitted bales - cannot delete if any are submitted
    submitted_bales = []
    for bales_name in bales_to_delete:
        docstatus = frappe.db.get_value("Bales", bales_name, "docstatus")
        if docstatus == 1:
            submitted_bales.append(bales_name)

    if submitted_bales:
        frappe.throw(
            _(
                "Cannot delete Stock Entry. The following Bales are submitted: {0}. "
                "Please cancel the Stock Entry first."
            ).format(", ".join(submitted_bales))
        )

    deleted_bales = []
    errors = []

    for bales_name in bales_to_delete:
        try:
            docstatus = frappe.db.get_value("Bales", bales_name, "docstatus")

            # Can only delete Draft (0) or Cancelled (2) Bales
            if docstatus in (0, 2):
                # First, clear the bales_id link in Bales Creator Item child table
                # This removes the back-link that Frappe checks during deletion
                frappe.db.sql("""
                    UPDATE `tabBales Creator Item`
                    SET bales_id = NULL
                    WHERE bales_id = %s
                """, (bales_name,))

                # Now delete the Bales document
                frappe.delete_doc(
                    "Bales",
                    bales_name,
                    force=1,
                    ignore_permissions=True
                )
                deleted_bales.append(bales_name)

        except frappe.DoesNotExistError:
            # Bales doesn't exist, skip
            pass
        except Exception as e:
            errors.append(f"{bales_name}: {str(e)}")
            frappe.log_error(
                message=str(e),
                title="Bales Delete Error"
            )

    if deleted_bales:
        frappe.msgprint(
            _("Deleted {0} Bales: {1}").format(
                len(deleted_bales), ", ".join(deleted_bales)
            ),
            indicator="orange",
            alert=True,
        )

    if errors:
        frappe.throw(
            _("Failed to delete some Bales: {0}").format("<br>".join(errors))
        )

# SET THE QTY to upperround
def roundqty(doc,method=None):
    if doc.items:
        for item in doc.items:
            if not item.is_scrap_item and not item.is_finished_item and (not "ink" in item.item_group.lower() and not "solvent" in item.item_group.lower()):
                item.qty = math.ceil(item.qty)


# ==================== NEW BALES FLOW FUNCTIONS ====================
# These functions implement the new bales creation flow from Manufacturing
# Note: Old Bales Creator flow is deprecated


def create_bales_from_manufacture_se(stock_entry_doc, method=None):
    """
    Create Bales when Manufacture Stock Entry is submitted.
    This is the NEW bales creation flow - directly from Manufacturing.

    Triggered on Stock Entry submit when:
    - stock_entry_type == "Manufacture"
    - job_card is linked (via custom_job_card_reference field)

    Uses frappe.enqueue with enqueue_after_commit=True to ensure
    Serial and Batch Bundles are fully created before bales processing.

    Args:
        stock_entry_doc: Stock Entry document
        method: Hook method name (optional)
    """
    # Only process Manufacture Stock Entries with Job Card
    if stock_entry_doc.stock_entry_type != "Manufacture":
        return

    # Job Card is linked via custom_job_card_reference field (not standard job_card)
    job_card_ref = getattr(stock_entry_doc, 'custom_job_card_reference', None)
    if not job_card_ref:
        return

    # Enqueue bales creation to run after database commit
    # This ensures Serial and Batch Bundles are fully created
    frappe.enqueue(
        method=_create_bales_after_commit,
        stock_entry_name=stock_entry_doc.name,
        job_card_ref=job_card_ref,
        enqueue_after_commit=True,
        queue="short"
    )


def _create_bales_after_commit(stock_entry_name, job_card_ref):
    """
    Internal function to create bales after database commit.
    Called via frappe.enqueue with enqueue_after_commit=True.
    """
    try:
        from tcb_manufacturing_customizations.bales_utils import (
            create_bales_from_manufacture
        )

        # Get fresh Stock Entry document with all Serial and Batch Bundles
        stock_entry_doc = frappe.get_doc("Stock Entry", stock_entry_name)

        created_bales = create_bales_from_manufacture(
            stock_entry_doc, job_card_ref
        )

        if created_bales:
            frappe.publish_realtime(
                "msgprint",
                {
                    "message": _("Created {0} Bales: {1}").format(
                        len(created_bales), ", ".join(created_bales)
                    ),
                    "indicator": "green",
                    "alert": True
                },
                user=frappe.session.user
            )
    except Exception as e:
        frappe.log_error(
            f"Error creating bales from Manufacture SE {stock_entry_name}: {str(e)}",
            "Bales Creation Error"
        )
        frappe.publish_realtime(
            "msgprint",
            {
                "message": _("Warning: Failed to create Bales. Check Error Log."),
                "indicator": "orange",
                "alert": True
            },
            user=frappe.session.user
        )


def cancel_bales_from_manufacture_se(stock_entry_doc, method=None):
    """
    Cancel Bales when Manufacture Stock Entry is cancelled.
    This handles the NEW bales flow cancellation.

    Args:
        stock_entry_doc: Stock Entry document
        method: Hook method name (optional)
    """
    # Only process Manufacture Stock Entries
    if stock_entry_doc.stock_entry_type != "Manufacture":
        return

    try:
        from tcb_manufacturing_customizations.bales_utils import \
            cancel_bales_from_stock_entry

        cancel_bales_from_stock_entry(stock_entry_doc)
    except Exception as e:
        frappe.log_error(
            f"Error cancelling bales from Manufacture SE {stock_entry_doc.name}: {str(e)}",
            "Bales Cancel Error"
        )


def populate_packaging_materials_on_transfer(stock_entry_doc, method=None):
    """
    Populate Job Card's packaging materials table when Material Transfer
    for Manufacture Stock Entry is submitted.

    This captures the raw materials used for manufacturing so they can
    be tracked when creating Bales.

    Args:
        stock_entry_doc: Stock Entry document
        method: Hook method name (optional)
    """
    # Only process Material Transfer for Manufacture
    if stock_entry_doc.stock_entry_type != "Material Transfer for Manufacture":
        return

    # Job Card can be linked via:
    # 1. custom_job_card_reference (custom field, set by custom make_stock_entry)
    # 2. job_card (standard ERPNext field, set when creating from Job Card)
    job_card_ref = getattr(stock_entry_doc, 'custom_job_card_reference', None)

    # Fallback to standard job_card field if custom field is not set
    if not job_card_ref:
        job_card_ref = getattr(stock_entry_doc, 'job_card', None)

    if not job_card_ref:
        return

    try:
        from tcb_manufacturing_customizations.bales_utils import \
            populate_job_card_packaging_materials

        populate_job_card_packaging_materials(stock_entry_doc, job_card_ref)
    except Exception as e:
        frappe.log_error(
            f"Error populating packaging materials for JC {job_card_ref}: {str(e)}",
            "Packaging Materials Error"
        )


def clear_packaging_materials_on_cancel(stock_entry_doc, method=None):
    """
    Clear Job Card's packaging materials when Material Transfer
    for Manufacture Stock Entry is cancelled.

    Args:
        stock_entry_doc: Stock Entry document
        method: Hook method name (optional)
    """
    # Only process Material Transfer for Manufacture
    if stock_entry_doc.stock_entry_type != "Material Transfer for Manufacture":
        return

    # Job Card can be linked via:
    # 1. custom_job_card_reference (custom field)
    # 2. job_card (standard ERPNext field)
    job_card_ref = getattr(stock_entry_doc, 'custom_job_card_reference', None)

    # Fallback to standard job_card field if custom field is not set
    if not job_card_ref:
        job_card_ref = getattr(stock_entry_doc, 'job_card', None)

    if not job_card_ref:
        return

    try:
        from tcb_manufacturing_customizations.bales_utils import \
            clear_job_card_packaging_materials

        clear_job_card_packaging_materials(stock_entry_doc, job_card_ref)
    except Exception as e:
        frappe.log_error(
            f"Error clearing packaging materials for JC {job_card_ref}: {str(e)}",
            "Packaging Materials Error"
        )
        
        
        
        
# TO UPDATE EXPENSES FOR ELECTRICITY AND WAGES
@frappe.whitelist()
def updateexpenses(doc, method=None):
    try:
        elec_ratio = 0
        wages_ratio = 0
        total_exp = 0
        elecacc = None
        wagesacc = None

        # Only for Manufacture Stock Entry with additional costs
        if doc.stock_entry_type == "Manufacture" and doc.additional_costs:
            total_exp = sum(addcost.amount for addcost in doc.additional_costs)

            if doc.custom_job_card_reference:
                jc_workstation = frappe.db.get_value(
                    "Job Card",
                    doc.custom_job_card_reference,
                    "workstation"
                )

                if jc_workstation:
                    workstation = frappe.get_doc("Workstation", jc_workstation)

                    elec_cost = workstation.hour_rate_electricity or 0
                    wages_cost = workstation.hour_rate_labour or 0

                    elecacc = workstation.custom_electricity_cost_account
                    wagesacc = workstation.custom_wages_cost_account

                    if elec_cost and not elecacc:
                        frappe.throw(
                            _("Please set Electricity Account in Accounts tab of Workstation.")
                        )

                    if wages_cost and not wagesacc:
                        frappe.throw(
                            _("Please set Wages Account in Accounts tab of Workstation.")
                        )

                    if elec_cost and wages_cost:
                        total_rate = elec_cost + wages_cost
                        elec_ratio = elec_cost / total_rate
                        wages_ratio = wages_cost / total_rate

        # Rebuild Additional Costs
        if elec_ratio and wages_ratio and total_exp:
            doc.additional_costs = []

            doc.append("additional_costs", {
                "expense_account": elecacc,
                "description": "Power Cost as per Work Order / BOM",
                "amount": total_exp * elec_ratio
            })

            doc.append("additional_costs", {
                "expense_account": wagesacc,
                "description": "Wages Cost as per Work Order / BOM",
                "amount": total_exp * wages_ratio
            })

    except Exception as e:
        frappe.log_error(
            title="Electricity and Wages Cost setting error",
            message=frappe.get_traceback()
        )
        frappe.throw(
            _("Failed to set Electricity and Wages Cost: {0}").format(str(e))
        )