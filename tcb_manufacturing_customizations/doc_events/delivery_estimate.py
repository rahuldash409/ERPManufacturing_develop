import frappe
from frappe.utils import today,add_days,add_to_date
from frappe.utils import flt
import time, datetime 

# @frappe.whitelist()
# def fill_so(docname,method=None):
#     de = frappe.get_doc("Delivery Estimate",docname)
#     # print("Docname is-------------------",docname)
#     de.existing_sales_orders = []
#     so_list = frappe.db.get_all("Sales Order",filters={"docstatus":1,"delivery_date":[">=",today()]},order_by="delivery_date desc",pluck="name")
#     # print("SO list -------------------",so_list)
#     for so in so_list:
#         order = frappe.get_doc("Sales Order",so)
#         if flt(order.per_delivered)<100:
#             de.append("existing_sales_orders",{
#             "sales_order":order.name,
#             "customer":order.customer,
#             "qty":order.total_qty,
#             "delivery_date":order.delivery_date,
#             "percentage_delivered":order.per_delivered
#         })
        
#     de.save()

@frappe.whitelist()
def get_sales_orders_data():
    
    so_list = frappe.db.get_all(
        "Sales Order",
        filters={
            "docstatus": 1,
            "per_delivered": ["<",100], 
            # "delivery_date": [">=", today()]
            
        },
        fields=["name", "customer", "total_qty", "delivery_date", "per_delivered"],
        order_by="delivery_date desc"
    )
    
    # Filter orders that are not 100% delivered
    pending_orders = []
    for so in so_list:
        production_percentage=0.0
        production_plan_against_so = frappe.get_value("Production Plan Sales Order",filters={
            "sales_order":so.name
        },fieldname="parent")
        # production_plan_against_so = frappe.get_all("Production Plan Sales Order",filters={
        #     "sales_order":so.name
        # },fields="parent",limit=1)
        # print('---here is the production plan agains so-=-',production_plan_against_so)
        # print('---here is the production plan agains so parent -=-',production_plan_against_so)
        if production_plan_against_so:
            prod_plan_doc = frappe.get_doc("Production Plan",production_plan_against_so)
            print('here is the proditon plan doc --',prod_plan_doc)
            production_percentage = (prod_plan_doc.total_produced_qty / prod_plan_doc.total_planned_qty) * 100
            print('here is the proditon plan doc pduction percenate  --',production_percentage)
            
            # width: (frm.doc.total_produced_qty / frm.doc.total_planned_qty) * 100 + "%",
        # print('here is the proditon plan doc pduction percenate  --',production_percentage)
        # print('here is the proditon plan doc   --',production_plan_against_so)
        
        if flt(so.per_delivered) < 100:
            pending_orders.append({
                "sales_order": so.name,
                "linked_production_plan": production_plan_against_so,
                "production_percentage": production_percentage,
                "customer": so.customer,
                "qty": so.total_qty,
                "delivery_date": so.delivery_date,
                "percentage_delivered": so.per_delivered,
            })
    return pending_orders
    
    

@frappe.whitelist()
def calculate_bom(client_doc, method=None):
    import json
    client_doc_dict = json.loads(client_doc)
    doc = frappe.get_doc("Delivery Estimate", client_doc_dict.get('name'))
    # print("----------this is the doc ------",doc)
    bom = client_doc_dict.get('bom')
    # print("----this is the bom ---",bom)
    doc.bom = bom
    d_qty = client_doc_dict.get('qty_to_deliver')
    doc.item_to_deliver = client_doc_dict.get('item_to_deliver')
    doc.qty_to_deliver = client_doc_dict.get('qty_to_deliver')
    # print("----this is the qty ---",d_qty)
    if not bom:
        return

    doc.table_ilpb = []

    base_bom = frappe.get_doc("BOM", bom)
    base_qty = base_bom.quantity
    change = ((d_qty - base_qty) / base_qty) if base_qty else 0

    for row in base_bom.items:
        doc.append("table_ilpb", {
            "item_code": row.item_code,
            "qty": row.qty * (1 + change),
            "actual_qty": row.custom_excess_qty * (1 + change),
            "uom": row.uom,
            "bom": row.bom_no,
        })
        
    to_process = [r for r in doc.table_ilpb if r.bom]
    processed_boms = set()

    while to_process:
        row = to_process.pop(0)
        if row.bom in processed_boms:
            continue
        processed_boms.add(row.bom)

        b = frappe.get_doc("BOM", row.bom)
        change = ((row.qty - b.quantity) / b.quantity) if b.quantity else 0

        for item in b.items:
            new_row = {
                "item_code": item.item_code,
                "qty": item.qty * (1 + change),
                "actual_qty": item.custom_excess_qty * (1 + change),
                "uom": item.uom,
                "bom": item.bom_no,
            }
            doc.append("table_ilpb", new_row)

            if item.bom_no:
                to_process.append(frappe._dict(new_row))

    # doc.save(ignore_permissions=True)
    # frappe.db.commit()
    return doc.as_dict()





@frappe.whitelist()
def check_employees(doc=None,method=None):
    jc_list = frappe.get_all("Job Card",filters={"status":["!=","Completed"]},fields=["name"],limit_page_length=100)
    # Created an object to store the doc with the employee name. Not needed
    # emp_list = {}
    # for jc in jc_list:
    #     jcard = frappe.get_doc("Job Card",jc["name"])
    #     for emp in jcard.employee:
    #         if emp.employee not in emp_list:
    #             emp_list[emp.employee] = []
    #             emp_doc = frappe.get_doc("Employee",emp.employee)
    #             emp_list[emp.employee] = emp_doc
    
    emp_list = set()
    for jc in jc_list:
        jcard = frappe.get_doc("Job Card",jc["name"])
        for emp in jcard.employee:
            emp_list.add(emp.employee)
    
    return emp_list
    # for emp, emp_doc in emp_list.items():
    #     doc.append("employee_details",{
    #         "employee":emp,
    #         "employee_name":emp_doc.employee_name,
    #         "holiday_list":emp_doc.holiday_list
    #     })
    
    
    
    
# @frappe.whitelist()
# def set_bom(docname=None, item=None, method=None):
#     # import json

#     # client_item = None
#     # client_bom = None
#     # # doc = frappe.get_doc("Delivery Estimate",docname)
#     # # print("-------------this is the document - ",document)
#     # if document:
#     #     try:
#     #         client_doc_dict = json.loads(document)
#     #         # print('----------document--------')
#     #         client_item = client_doc_dict.get('item_to_deliver')
#     #         client_bom = client_doc_dict.get('bom')
#     #         # get default BOM
#     #         bom = frappe.get_last_doc("BOM", filters={"item": client_item, "is_default": 1}, order_by="modified desc")
#     #         # print('--------here is the bom - ',bom)

#     #         if bom and not client_bom:
#     #             return bom.name
#     #         else:
#     #             frappe.throw('No attached BOM found for this item.')
#     #     except Exception as e:
#     #         frappe.log_error("set_bom error",f"Invalid JSON in document: {document}")

#     # if not document:
#     #     doc = frappe.get_doc("Delivery Estimate",docname)
        
        
        
#     # Agar direct 'item' arg aaya hai 
#     # if not client_item and item:
#     #     client_item = item
#     # print("-------------this is the document - ",client_item)

    
    
#     return None

@frappe.whitelist()
def calculate_lead_time(docname,method=None):
    doc = frappe.get_doc("Delivery Estimate",docname)
    doc.deficit_item_wise_lead_time=[]
    # SET is only for singular values,, not for key value structures
    # deficit_items = set()
    # if doc.warehouse_wise_stock:
    #     for item in doc.warehouse_wise_stock:
    #         if item.deficit_qty and item.item not in deficit_items:
    #             deficit_items.add(item.item)
    deficit_items = {}
    if doc.warehouse_wise_stock:
        for item in doc.warehouse_wise_stock:
            if item.net_deficit_qty and item.item: 
                if item.item not in deficit_items:
                    item_doc = frappe.get_doc("Item",item.item)
                    deficit_items[item.item] = []
                    # deficit_items[item.item].append(item.deficit_qty)
                    deficit_items[item.item].append(item.net_deficit_qty)
                    deficit_items[item.item].append(item_doc.custom_supplier_wise_lead_time)
                # Incorrect way
                # deficit_items[item] = []
                # deficit_items.append(item.deficit_qty)
    
    if deficit_items:
        to_remove = set()
        for item_code, data in deficit_items.items():
            deficit_qty = data[0]
            supplier_data = data[1]

            doc.append("deficit_item_wise_lead_time",{
                        "item":item_code,
                        "deficit_qty":deficit_qty,
                        "supplier":"",
                        "lead_time_taken_in_days":""
                    })
            if supplier_data:
                to_remove.add(item_code)
                for row in supplier_data:
                    doc.append("deficit_item_wise_lead_time",{
                        "item":item_code,
                        "deficit_qty":deficit_qty,
                        "supplier":row.supplier,
                        "lead_time_taken_in_days":row.lead_time_taken_in_days
                    })
        doc.set("deficit_item_wise_lead_time", [
        row for row in doc.deficit_item_wise_lead_time
        if not (row.item in to_remove and not row.supplier)])
    for i, row in enumerate(doc.deficit_item_wise_lead_time, start=1):
        row.idx = i
        
    doc.save()
    
    
# set the lead time
@frappe.whitelist()
def calculate_procurement_lead_time(docname,method=None): 
    doc = frappe.get_doc("Delivery Estimate",docname)   
    unique_items =  {}
    for items in doc.deficit_item_wise_lead_time:
        if items.item not in unique_items:
            unique_items[items.item]=[]
        if items.lead_time_taken_in_days and items.supplier:
            unique_items[items.item].append(items.lead_time_taken_in_days)            
        # print("UNIQUE ITEMSSS---------------",unique_items)
    
    max_days = 0
    for item_c, days_taken in unique_items.items():
        if days_taken:
            # print('Daysss --- takennn --------------',days_taken,"---------------")
            if min(days_taken)>max_days:
                max_days = min(days_taken)
    
    selected_days = frappe.db.sql("""
            SELECT lead_time_taken_in_days
            FROM `tabDelivery Estimate Deficit Item` 
            WHERE parent = %s and `select` = "1" 
        """,(docname),as_dict=1)
    # print("----------------------selected dayssss--------",selected_days)
    for days in selected_days:
        # print("----------------------dayssssss----",days)
        if int(days.lead_time_taken_in_days) > max_days:
            max_days = days.lead_time_taken_in_days
    doc.procurement_lead_time_taken_in_days = max_days
    doc.save()


@frappe.whitelist()
def calculate_delivery_date(docname,method=None): 
    doc                         = frappe.get_doc("Delivery Estimate",docname) 
    today_date = frappe.utils.getdate(frappe.utils.today())
    highest_sale_order_date     = doc.existing_sales_orders[0].delivery_date
    doc.last_sales_order_delivery_date = highest_sale_order_date
    initial_process_days        = (doc.max_workstation_lead_time_in_days + doc.procurement_lead_time_taken_in_days 
                                    + doc.estimated_operation_completion_time_in_days + doc.days_to_complete_the_order 
                                    + doc.shipping_transit_time_days + doc.buffer_days_if_needed) 
    
    #with sales order and without holidays fields assignment
    days_btw_today_and_highest_sale_order_date = highest_sale_order_date - today_date
    # print('days btw -------------',days_btw_today_and_highest_sale_order_date.days , '---tyepe -----',type(days_btw_today_and_highest_sale_order_date))
    process_days_after_last_so_delivery_var = (days_btw_today_and_highest_sale_order_date.days) +  initial_process_days
    doc.process_days_after_last_so_delivery = process_days_after_last_so_delivery_var
    
    process_days_including_sales_order_without_holidays_date_var = add_to_date(today_date,days=process_days_after_last_so_delivery_var)
    doc.process_days_including_sales_order_without_holidays_date = process_days_including_sales_order_without_holidays_date_var
    
    #Process Days 
    total_processing_working_days = (doc.max_workstation_lead_time_in_days + doc.procurement_lead_time_taken_in_days 
                                    + doc.estimated_operation_completion_time_in_days + doc.days_to_complete_the_order 
                                    + doc.shipping_transit_time_days + doc.buffer_days_if_needed)
    doc.process_days = total_processing_working_days
    estimate_process_days_date = add_to_date(today_date,days=total_processing_working_days)
    
    
    # print("----------",today())
    # print('initial process daysss  very initially   - --------------------',initial_process_days,'---------------------')
    doc.recommended_delivery_date = estimate_process_days_date
    added_process_days          = 0
    estimate_date               = add_to_date(highest_sale_order_date ,days=initial_process_days)
    if doc.holiday_list :
        holiday_doc = frappe.get_doc("Holiday List",doc.holiday_list) 
        # holiday_table_doc = frappe.get_doc("Holiday",holiday_doc.name)
        old_holiday_count = 0 
        old_process_days_holiday_count = 0
        # holidays_btw_dates = 0
        if highest_sale_order_date > holiday_doc.to_date:
            frappe.throw("The Holiday List Is Too Old!!")
            return
        # if highest_sale_order_date < holiday_doc.from_date:
        #     frappe.throw("The Holiday List's From Date Is Not Started Yet!! Please Attatch Valid Holiday List.")
        #     return
        # while(holidays_btw_dates is not 
        while holiday_doc:
            holidays_btw_dates = 0
            estimate_date = add_to_date(highest_sale_order_date ,days=initial_process_days)
            holidays_btw_process_days = 0
            estimate_process_days_date = add_to_date(today_date,days=total_processing_working_days)
            # print('--------------estimate Date ---',estimate_date,'-------------------------------')
            # holidays_btw_dates_dict = frappe.db.sql("""
            #                                 SELECT COUNT(name) as days_count
            #                                 FROM `tabHoliday` where parent = %s and  holiday_date BETWEEN %s and %s  LIMIT 1
            #                                 """,(doc.holiday_list,highest_sale_order_date,estimate_date),as_dict=1)[0]
            
            for line in holiday_doc.holidays :
                if line.holiday_date >= highest_sale_order_date and line.holiday_date <= estimate_date :
                    # print('---------------------4444987-------------------------00000000000000000000000000000000000',line.holiday_date)
                    holidays_btw_dates += 1 
                    
                if line.holiday_date >= today_date and line.holiday_date <= estimate_process_days_date :
                    # print('----the -----------------444444444444444444444444444400000000000000000000000000000000000',estimate_process_days_date)
                    holidays_btw_process_days += 1 
                # print("-------------ye le holideay btw datesss----------",holidays_btw_dates,"\n0000000000--------------oldholidady cont",old_holiday_count)
            # holidays_btw_dates = days_count
            # print('-------------holidays_btw_dates----------',(holidays_btw_dates),"-----------------------")
            # print('-------------holidays_btw_dates deducted by old holidays ----------',(holidays_btw_dates-old_holiday_count),"-----------------------")
            
            if (holidays_btw_dates!=old_holiday_count):
                added_process_days = initial_process_days + holidays_btw_dates - old_holiday_count
                initial_process_days = added_process_days
                old_holiday_count = holidays_btw_dates
                
            if (holidays_btw_process_days!=old_process_days_holiday_count):
                added_process_days_with_holiday = total_processing_working_days + holidays_btw_process_days - old_process_days_holiday_count
                total_processing_working_days = added_process_days_with_holiday
                old_process_days_holiday_count = holidays_btw_process_days
                # print('added process days - --------------------',added_process_days,'---------------------')
                # print('estimate date while assingg in the variable  - --------------------',estimate_date,'---------------------')
                # print('initial process daysss  while assingg in the variable  - --------------------',initial_process_days,'---------------------')
                doc.days_with_sales_order_and_holidays_included_date = add_to_date(highest_sale_order_date ,days=initial_process_days)
                doc.days_with_sales_order_and_holidays_included = initial_process_days + days_btw_today_and_highest_sale_order_date.days
                doc.process_days_including_holidays_date = add_to_date(today_date,days=total_processing_working_days)
                doc.process_days_including_holidays = total_processing_working_days
                doc.save()
            else:
                doc.days_with_sales_order_and_holidays_included_date = add_to_date(highest_sale_order_date ,days=initial_process_days)
                doc.days_with_sales_order_and_holidays_included = initial_process_days  + days_btw_today_and_highest_sale_order_date.days
                doc.save()
                
                doc.process_days_including_holidays_date = add_to_date(today_date,days=total_processing_working_days)
                doc.process_days_including_holidays = total_processing_working_days 
                
                break
    else:
        doc.days_with_sales_order_and_holidays_included_date = estimate_date
        doc.days_with_sales_order_and_holidays_included = initial_process_days + days_btw_today_and_highest_sale_order_date.days
        
        doc.process_days_including_holidays_date = add_to_date(today_date,days=total_processing_working_days)
        doc.process_days_including_holidays = total_processing_working_days
        doc.save()
    
    # print('-------------------------highest date....dateeeee---',highest_date)

    # print('-------------------------recommended_delivery_date....dateeeee---',doc.recommended_delivery_date)

    # print('----------------------------------')
    doc.save()
    
        

# @frappe.whitelist()
# def calculate_delivery_date(docname,method=None): 
#     doc                         = frappe.get_doc("Delivery Estimate",docname) 
#     highest_sale_order_date     = doc.existing_sales_orders[0].delivery_date 
#     initial_process_days        = doc.procurement_lead_time_taken_in_days + doc.estimated_operation_completion_time_in_days + doc.days_to_complete_the_order + doc.shipping_transit_time_days
#     print('initial process daysss  very initially   - --------------------',initial_process_days,'---------------------')
#     added_process_days          = 0
#     estimate_date               = add_to_date(highest_sale_order_date ,days=initial_process_days)
#     if doc.holiday_list :
#         holiday_doc = frappe.get_doc("Holiday List",doc.holiday_list) 
#         # holidays_btw_dates_dict = frappe.db.sql(""" 
#         #                                     SELECT COUNT(name) as days_count
#         #                                     FROM `tabHoliday` where parent = %s and  holiday_date BETWEEN %s and %s  LIMIT 1
#         #                                     """,(doc.holiday_list,highest_sale_order_date,estimate_date),as_dict=1)[0]
#         old_holiday_count = 0 
#         if highest_sale_order_date > holiday_doc.to_date:
#             frappe.throw("The Holiday List Is Too Old!!")
#             return
#         if highest_sale_order_date < holiday_doc.from_date:
#             frappe.throw("The Holiday List's From Date Is Not Started Yet!! Please Attatch Valid Holiday List.")
#             return
#         # while(holidays_btw_dates is not 
#         while holiday_doc:
#             estimate_date = add_to_date(highest_sale_order_date ,days=initial_process_days)
#             print('--------------estimate Date ---',estimate_date,'-------------------------------')
#             holidays_btw_dates_dict = frappe.db.sql(""" 
#                                             SELECT COUNT(name) as days_count
#                                             FROM `tabHoliday` where parent = %s and  holiday_date BETWEEN %s and %s  LIMIT 1
#                                             """,(doc.holiday_list,highest_sale_order_date,estimate_date),as_dict=1)[0]
#             holidays_btw_dates = holidays_btw_dates_dict.days_count
#             print('-------------holidays_btw_dates----------',(holidays_btw_dates),"-----------------------")
#             print('-------------holidays_btw_dates deducted by old holidays ----------',(holidays_btw_dates-old_holiday_count),"-----------------------")
            
#             if (holidays_btw_dates!=old_holiday_count):
#                 added_process_days = initial_process_days + holidays_btw_dates - old_holiday_count
#                 initial_process_days = added_process_days
#                 old_holiday_count = holidays_btw_dates
#                 print('added process days - --------------------',added_process_days,'---------------------')
#                 print('estimate date while assingg in the variable  - --------------------',estimate_date,'---------------------')
#                 print('initial process daysss  while assingg in the variable  - --------------------',initial_process_days,'---------------------')
#                 doc.recommended_delivery_date = add_to_date(highest_sale_order_date ,days=initial_process_days)
#                 doc.process_days = initial_process_days
#                 doc.save()
#             else:
#                 break
#     else:
#         doc.recommended_delivery_date = estimate_date
#         doc.process_days = initial_process_days
#         doc.save()
    
#     # print('-------------------------highest date....dateeeee---',highest_date)
    
#     print('-------------------------recommended_delivery_date....dateeeee---',doc.recommended_delivery_date)

#     # print('----------------------------------')
#     doc.save()
    
@frappe.whitelist()
def get_employees_jobwise(docname=None,method=None):
        
    doc = frappe.get_doc("Delivery Estimate",docname)   
    employees_list_dict = frappe.db.sql("""
                                        
                                        SELECT jc.name as JobName,emp.name as EmpID ,jctg.parentfield
                                        from `tabJob Card` as jc 
                                        join `tabJob Card Time Log` as jctg on  jc.name = jctg.parent 
                                        right join `tabEmployee` as emp on jctg.employee = emp.name
                                        WHERE  jc.docstatus not in (1,2) AND jctg.parentfield ='employee'  or jc.docstatus is Null 
                                        order by jc.name is Null DESC ,emp.employee_name
                                        
                                        # SELECT emp.name as EmpID,emp.employee_name as EmpName, jctg.parent as JobName, jctg.employee 
                                        # from `tabEmployee` as emp 
                                        # right join `tabJob Card Time Log` as jctg on  emp.name = jctg.employee 
                                        # join `tabJob Card` as  jc on jctg.parent = jc.name 
                                        # WHERE  jc.docstatus not in (1,2) or jc.docstatus is Null
                                        # order by jc.name is Null DESC ,emp.employee_name
                                        
                                        # select jc.name, jc.docstatus,employee, parent, status
                                        # from    `tabJob Card Time Log`  as jctg
                                        # join `tabJob Card` as  jc on jctg.parent = jc.name 
                                        # WHERE  jc.docstatus not in (1,2) or jc.docstatus is Null

                                        """,as_dict=1)
    # print("---------------------------------------------------------------------------------------")
    for emp in employees_list_dict:
        # print('-----------empppppssss------',emp)
        doc.append("employee_details", {
                "employee": emp.EmpID,
                "job_card": emp.JobName,
                
            })
    doc.save()
        
    # print("---------------------------------------------------------------------------------------")
    
@frappe.whitelist()
def get_employee_leave_list(docname=None,method=None):
    doc=frappe.get_doc("Delivery Estimate",docname)
    # highest_sale_order_date = doc.existing_sales_orders[0].delivery_date 
    
    all_leave_application_of_slot = frappe.get_all("Leave Application",
        filters={
            "docstatus": 1,
            "status": "Approved",
            # "from_date": [">=",highest_sale_order_date],
            "to_date": [">=",today()]
        }
    )
    if all_leave_application_of_slot:
        doc.employee_leave_list = []
        for leave in all_leave_application_of_slot:
            doc.append("employee_leave_list",{
                'leave_application_id':leave.name
            })
    # print("-----------------------------------",all_leave_application_of_slot)
    doc.save()
    
    
        
        
        
# Calculate Production Details
@frappe.whitelist()
def calc_prod_details(docname=None,method=None):
    doc = frappe.get_doc("Delivery Estimate",docname)
    if doc.table_ilpb:
        bom = {}
        for row in doc.table_ilpb:
            if row.item_code not in bom and row.bom and row.qty:
                bom[row.item_code] = [row.bom,row.qty]
        doc.operations_and_workstations = []
        for i,details in bom.items():
            document = details[0]
            qty = details[1]
            req_bom = frappe.get_doc("BOM",document)
            bom_qty = req_bom.quantity
            opn_time = sum(opn.time_in_mins for opn in req_bom.operations)
            increase = ((qty*100)/bom_qty)/100
            
            # Field 1-> Operation Time increase as per qty
            # Day set as 8 hours
            time_inc = opn_time*increase
            for opn in req_bom.operations:
                doc.append("operations_and_workstations",{
                    "bom":document,
                    "operation":opn.operation,
                    "workstation":opn.workstation,
                    "estimated_time":time_inc,
                    "estimated_time_in_days":(time_inc/60)/8
                })
    doc.save()

# import frappe

# def get_supplier_wise_lead_time_of_items_cron(insert_to_doctype=False):
#     """
#     Produces rows: (serial, item_code, item_name, supplier, avg_lead_time_days, total_receipts)
#     If insert_to_doctype=True it will upsert into DocType "Supplier Item Lead Time" with keys (supplier,item_code).
#     Make sure that DocType exists with fields: supplier (Link), item_code, item_name, avg_lead_time, total_receipts, last_updated
#     """

#     rows = frappe.db.sql(
#         """
#         SELECT
#             prt.item_code AS item_code,
#             prt.item_name AS item_name,
#             po.supplier AS supplier,
#             AVG(DATEDIFF(pr.posting_date, po.transaction_date)) AS avg_lead_time,
#             COUNT(*) AS total_receipts
#         FROM `tabPurchase Receipt Item` prt
#         JOIN `tabPurchase Receipt` pr ON prt.parent = pr.name
#         LEFT JOIN `tabPurchase Order` po ON prt.purchase_order = po.name
#         WHERE prt.docstatus = 1
#         GROUP BY prt.item_code, po.supplier
#         ORDER BY prt.item_code, po.supplier
#         """,
#         as_dict=1
#     )

#     print("\n\n========= Supplier × Item — Average Lead Time (days) =========\n")
#     for idx, r in enumerate(rows, start=1):
#         item = r.get("item_code") or ""
#         item_name = r.get("item_name") or ""
#         supplier = r.get("supplier") or "UNSPECIFIED"
#         avg_days = float(r.get("avg_lead_time") or 0)
#         total = int(r.get("total_receipts") or 0)

#         # Print row with serial
#         print("---------------------------------------------------------")
#         print(f"{idx}. Supplier: {supplier}  |  Item: {item}  ({item_name})")
#         print(f"    Avg Lead Time: {avg_days:.2f} days  |  Total Receipts: {total}")
#         print("---------------------------------------------------------")

#         # Optional: upsert into DocType
#         if insert_to_doctype:
#             try:
#                 # Use filter keys to find existing
#                 existing_name = frappe.db.exists(
#                     "Supplier Item Lead Time",
#                     {"supplier": supplier, "item_code": item}
#                 )
#                 if existing_name:
#                     doc = frappe.get_doc("Supplier Item Lead Time", existing_name)
#                     doc.avg_lead_time = avg_days
#                     doc.total_receipts = total
#                     doc.item_name = item_name
#                     doc.last_updated = frappe.utils.now()
#                     doc.save(ignore_permissions=True)
#                 else:
#                     frappe.get_doc({
#                         "doctype": "Supplier Item Lead Time",
#                         "supplier": supplier,
#                         "item_code": item,
#                         "item_name": item_name,
#                         "avg_lead_time": avg_days,
#                         "total_receipts": total,
#                         "last_updated": frappe.utils.now()
#                     }).insert(ignore_permissions=True)
#             except Exception as e:
#                 # fail quietly but inform in logs
#                 frappe.log_error(f"Failed upsert Supplier Item Lead Time for {supplier}/{item}: {e}")

#     if insert_to_doctype:
#         frappe.db.commit()

from frappe.utils import flt
@frappe.whitelist()
def get_supplier_wise_lead_time_of_items_cron():
    """
    Cron job to calculate and update supplier-wise lead times for all items
    Updates the 'Delivery Estimate Item Supplier' child table in Item doctype
    """
    try:
        all_purchase_rcpt_items = frappe.db.sql(
            """
            SELECT 
                po.supplier as supplier,
                prt.item_code as item_code,
                prt.item_name as item_name,
                (DATEDIFF(pr.posting_date, po.transaction_date)) AS lead_days
            FROM `tabPurchase Receipt Item` prt
            JOIN `tabPurchase Receipt` pr ON prt.parent = pr.name
            LEFT JOIN `tabPurchase Order` po ON prt.purchase_order = po.name
            LEFT JOIN `tabPurchase Order Item` poi on prt.purchase_order = poi.parent 
            WHERE prt.docstatus = 1
            AND po.supplier IS NOT NULL
            AND prt.item_code IS NOT NULL
            AND po.transaction_date IS NOT NULL
            AND pr.posting_date IS NOT NULL
            AND prt.received_qty = poi.qty
            AND DATEDIFF(pr.posting_date, po.transaction_date) >= 0
            ORDER BY prt.item_code, po.supplier
            """,
            as_dict=1
        )

        if not all_purchase_rcpt_items:
            frappe.log_error("No purchase receipt items found with valid lead times")
            return

        # print(f'\n========= Processing {len(all_purchase_rcpt_items)} Purchase Receipt Items =========\n')

        item_supplier_lead_times = {}
        
        for rcpt in all_purchase_rcpt_items:
            item_code = rcpt.item_code
            supplier = rcpt.supplier
            lead_days = flt(rcpt.lead_days)
            
            if item_code not in item_supplier_lead_times:
                item_supplier_lead_times[item_code] = {}
            if supplier not in item_supplier_lead_times[item_code]:
                item_supplier_lead_times[item_code][supplier] = []
            item_supplier_lead_times[item_code][supplier].append(lead_days)
            
        processed_items = 0
        total_suppliers_added = 0
        
        for item_code, supplier_data in item_supplier_lead_times.items():
            try:
                if not frappe.db.exists("Item", item_code):
                    frappe.log_error(f"Item {item_code} does not exist, skipping...")
                    # print(f"Item {item_code} does not exist, skipping...")
                    continue
                item_doc = frappe.get_doc("Item", item_code)
                item_doc.custom_supplier_wise_lead_time = []
                # print("=============================", supplier_data)
                for supplier, lead_times in supplier_data.items():
                    avg_lead_time = sum(lead_times) / len(lead_times)
                    
                    item_doc.append("custom_supplier_wise_lead_time", {
                        "supplier": supplier,
                        "lead_time_taken_in_days": round(avg_lead_time, 2)
                    })
                    total_suppliers_added += 1
                    print("--------------------here is the item name-",item_doc.name)
                item_doc.flags.ignore_permissions = True
                item_doc.flags.ignore_mandatory = True
                item_doc.save()
                
                processed_items += 1
                print(f"Updated Item: {item_code} with {len(supplier_data)} suppliers")
                
            except Exception as e:
                # print(f"Error processing item {item_code}: {str(e)}")
                frappe.log_error(f"Error in supplier lead time cron for item {item_code}: {str(e)}")
                continue
        
        frappe.db.commit()
        
        # print(f'\n========= Cron Job Completed Successfully =========')
        # print(f'Total Items Processed: {processed_items}')
        # print(f'Total Supplier Entries Added: {total_suppliers_added}')
        # print(f'========= End of Process =========\n')
        
        return {
            "status": "success",
            "items_processed": processed_items,
            "supplier_entries_added": total_suppliers_added
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_supplier_wise_lead_time_of_items_cron: {str(e)}")
        # print(f"Error in cron job: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_item_wise_workstation(docname=None,method=None):
    doc = frappe.get_doc("Delivery Estimate",docname)
    
    if doc.table_ilpb:
        doc.workstation_specifications = []
        for item in doc.table_ilpb:
            if not item.bom:
                continue
            else:
                # item_doc = frappe.get_doc("Item",item.item_code)
                workstation_speed_doc = frappe.get_all("Item Wise Workstation Speed",filters={
                    "parent" : item.item_code,
                    
                },fields=["parent","workstation","item_per_minute"],
                        order_by="item_per_minute asc",
                        limit_page_length=1
                )
                # print(workstation_speed_doc)
                # print("-----------------------------",len(workstation_speed_doc))
                for workstation in workstation_speed_doc:
                    workstaion_doc = frappe.get_doc("Workstation",workstation.workstation)
                    # item_per_minute=
                    # print("----------------ye pe worksationasss--",workstation.workstation)
                    # print("----------------ye pe itemsper minute--",workstation.item_per_minute)
                    # print("----------------days to compelte the order",doc.qty_to_deliver/(workstation_working_hours_in_a_day))
                    doc.append("workstation_specifications",{
                        "item":item.item_code,
                        "item_bom":item.bom,
                        "workstation" : workstation.workstation,
                        "item_per_minute" : workstation.item_per_minute,
                        "item_per_hour":workstation.item_per_minute*60,
                        "item_per_day":(workstaion_doc.total_working_hours or 1)*(workstation.item_per_minute*60),
                        "days_to_complete_the_order":[r.required_qty for r in doc.warehouse_wise_stock if r.item == item.item_code][0]/((workstaion_doc.total_working_hours or 1)*(workstation.item_per_minute*60))
                    })
                    # for  r in doc.warehouse_wise_stock:
                    #     print("---------------rq--",r.item)
                    # rqrd = 
                    # print('-----rwset --',rqrd)
                if doc.workstation_specifications:
                    doc.max_workstation_lead_time_in_days = max((l.days_to_complete_the_order for l in doc.workstation_specifications if l.days_to_complete_the_order))
                        # to_process = [r for r in doc.table_ilpb if r.bom]
                    # sum(opn.time_in_mins for opn in req_bom.operations)
                    # print("-------------days to complete the order--",doc.qty_to_deliver/workstaion_doc.total_working_hours)
                    # doc.save()
    doc.save()
    
    
    
@frappe.whitelist()
def workstation_query_for_item(doctype, searchfield,txt, start, page_len, filters):
    item_code = filters.get("item_code")
    if not item_code:
        return []
    
    result = frappe.db.sql("""
        SELECT DISTINCT iwws.workstation
        FROM `tabItem Wise Workstation Speed` iwws
        WHERE iwws.parent = %s
        LIMIT %s OFFSET %s
    """, (item_code, page_len, start), as_dict=False)
    
    return result

