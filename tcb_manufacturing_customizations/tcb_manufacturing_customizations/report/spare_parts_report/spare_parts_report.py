# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe
from  frappe.utils  import days_diff,add_days,today
sent_for_repair_status = "Sent For Repair"
consumable_spares_item_group = "Consumable Spares"
store_spares_item_group = "Store Spares"
repairable_spares_item_group = "Repairable Spares"

# repairable_spare_report_type = 
def execute(filters=None):
    data = []
    total_records = 0
    spares_consumption_stock_entry_type = "Spares Consumption"

    
    filters = filters or {}
    spare_report_type = filters.get('spare_report_type')
    # ##print('===================  spare report type ==',spare_report_type)
    
    if spare_report_type == repairable_spares_item_group:
        
        repairables_columns = [
            {"fieldname":"id","label":"Id","fieldtype":"Link","options":"Workstation Spare Parts","width":180},
            {"fieldname":"workstation","label":"Workstation","fieldtype":"Link","options":"Workstation","width":160},
            {"fieldname":"spare_part","label":"Spare Part","fieldtype":"Link","options":"Item","width":150},
            {"fieldname":"serial_no","label":"Serial No.","fieldtype":"Link","options":"Serial No","width":150},
            # {"fieldname":"spare_qty","label":"Spare Qty","fieldtype":"Float","width":100},
            {"fieldname":"date_of_installation","label":"Date of Installation","fieldtype":"Date","width":160},
            # {"fieldname":"dispose_replacement_date","label":"Dispose/Replacement Date","fieldtype":"Date","width":160},
            {"fieldname":"service_life_days_this_workstation","label":"Service Life (Days)","fieldtype":"Data","width":160},
            {"fieldname":"spare_status","label":"Status","fieldtype":"Char","width":160},
            
            
            {"fieldname":"repair_count","label":"Repair Count","fieldtype":"Char","width":160},
            {"fieldname":"operating_days_until_repair","label":"Operating Days Until Repair","fieldtype":"Data","width":160}, # Spares given Service how much days until this repair
            #  Damaged marked on date 
            {"fieldname":"damaged_marked_date","label":"Damaged Marked Date","fieldtype":"Date","width":160},
            {"fieldname":"repair_from_date","label":"Repiar From Date","fieldtype":"Date","width":160},
            # {"fieldname":"from_date_history_doc","label":"From date doc","fieldtype":"Link","options":"Spares Move History","width":160},
            
            {"fieldname":"repair_to_date","label":"Repiar To Date","fieldtype":"Date","width":160},
            # {"fieldname":"from_to_history_doc","label":"To date doc","fieldtype":"Link","options":"Spares Move History","width":160},
            
            {"fieldname":"repairing_time","label":"Repairing Time(Days)","fieldtype":"Data","width":160}, # Under Repairing Days
            # Service Request 
            {"fieldname":"service_request","label":"Service Request","fieldtype":"Link","options":"Service Request","width":160},
            {"fieldname":"repairing_vendor","label":"Vendor","fieldtype":"Link","options":"Supplier","width":160},
            {"fieldname":"po","label":"PO","fieldtype":"Link","options":"Purchase Order","width":160},
            
        ]
    # ###print('------------------',filters)
        conditions = {}
        conditions['docstatus'] = 1
        installation_from_date, installation_to_date = filters.get("entry_date_range") or [None, None]

        if installation_from_date and installation_to_date :
            conditions['date_of_installation'] = ["between",[installation_from_date,installation_to_date]]
        
        # if dispose_from_date and dispose_to_date:
        #     conditions['dispose_replacement_date'] = ["between",[dispose_from_date,dispose_to_date]]
        
        
        # ###print('----------------------dispose========= ',dispose_from_date,dispose_to_date)
        # ###print('------================isntalllation == ',installation_from_date,installation_to_date)
        # ###print('this is the codnition of the date fo instlaltion -===',conditions)
        
        if filters.get('workstation'):
            conditions['workstation'] = ['in' ,filters.get('workstation') ]
            
        if filters.get('spare_part'):
            conditions['spare_part'] = ['in' ,filters.get('spare_part') ]
            


        if filters.get('spare_status'):
            conditions['spare_status'] = ['in' ,filters.get('spare_status') ]
        
        all_workstations_parts = frappe.get_all("Workstation Spare Parts",filters=conditions,
                                            fields=[
                                                    "name","workstation", "spare_part", "date_of_installation",
                                                    "modified","service_life_days",
                                                    "spare_status","item_serial_number"
                                                    ])
    # for 
        if all_workstations_parts:
            total_records = len(all_workstations_parts)
            # #print('============== her is hte all recoreds - ', total_records)
        for part in all_workstations_parts:
            ##print('============= name ==',part.name)
            ##print("==============================================================================")
            spare_move_history_list = frappe.db.get_list("Spares Move History",filters={
                                                            "spare_entry_reference": part.name,
                                                            # "current_status":['in',['Sent For Repair','In Use','Scrapped','Available','Used In another Workstation']],
                                                            "is_stock_entry_submitted":True,
                                                            "ignored_history":False
                                                            },fields=['*'],order_by = "creation asc")
            service_start_date = None
            service_life = 0
            service_life_till_today = 0
            i = 0
            for his in spare_move_history_list:
                #print('================== history name ==================',his.item_serial_number)
                i += 1 # service life start from here ==================
                if (his.current_status == "In Use"):
                    ##print('eyeeeeeee--=====',his.name)
                    service_start_date = his.entry_date
                    service_life_till_today = days_diff(today(),his.entry_date)
                    if i == len(spare_move_history_list):
                        service_life = service_life + service_life_till_today
                    #print('here is the ----====',service_life_till_today)
                    #print('service start date ===',service_start_date)
                    # data.append({'service_life_days_this_workstation':(days_diff(today(),his.entry_date))})

                elif his.old_status == "In Use" and service_start_date and his.entry_date > service_start_date:
                    # #print('eeeeeeeeeeee eo  oldd status ===',his.old_status)
                    
                    service_end_date = his.entry_date
                    service_life += days_diff(service_end_date,service_start_date)
                    #print('breakdown ==',service_start_date,"-",service_end_date ,"=",service_life )
                    ##print()
                    ##print()
            #print('================== total service life till now ==================',service_life)
            data.append({
                "id": part.name,                  
                "workstation": part.workstation,                  
                "spare_part": part.spare_part, 
                "spare_qty" : part.spare_qty,
                "date_of_installation": part.date_of_installation, 
                "dispose_replacement_date":part.dispose_replacement_date,
                "service_life_days_this_workstation":service_life if service_life > 0 else service_life_till_today,
                "spare_status":part.spare_status,
                "serial_no":part.item_serial_number
            })
            ##print("==============================================================================")
            ##print()
            ##print()
            ##print()
            ##print()
            
                    # data['service_life_days_this_workstation'] = service_life_till_today
                    
            # repair_count  = 0 
            # # temp = 0
            # i = 0
            # repair_cycle_row = {}
            # from_creation = None
            # previous_to_date = None
            # for history in spare_move_history_list:
            #     # #print("================== history name ==================",history.name)
            #     i += 1
            #     if history.current_status == "In Use":
            #         service_start_date = history.entry_date

            #     elif history.current_status == "Damaged" and service_start_date:
            #         # STOP operation here
            #         service_life += days_diff(history.entry_date, service_start_date)
            #         last_operation_end_date = history.entry_date
            #         service_start_date = None

            #         # store damaged date for next repair cycle
            #         repair_cycle_row["damaged_marked_date"] = history.entry_date
            #     # repair_cycle_row['repair_to_date'] = ""
            #     elif history.current_status == sent_for_repair_status:
            #         repair_count +=1
            #         repair_cycle_row['repair_count'] = repair_count
            #         from_creation = history.creation
            #         # operating_days_until_epair = days_diff((part.date_of_installation if repair_count == 1 else history.entry_date))
            #         repair_from_date = history.entry_date
            #         repair_cycle_row['repair_from_date'] = repair_from_date
            #         vendor = ""
            #         if history.repair_po_reference:
            #             vendor = frappe.db.get_value("Purchase Order",history.repair_po_reference,"supplier")
            #             if vendor:
            #                 repair_cycle_row['repairing_vendor'] = vendor
                            
            #             ###print('her eihs the vendor ==',vendor)
            #         repair_cycle_row['po'] = history.repair_po_reference
            #         repair_cycle_row['service_request'] = history.service_request_reference
            #         repair_cycle_row['from_date_history_doc'] = history.name
                    
            #         repair_cycle_row['repairing_time'] = days_diff(today(),repair_cycle_row['repair_from_date'])
                    
            #         # operating_days_until_repair = days_diff(today(),(part.date_of_installation if repair_count == 1 else repair_cycle_row['repair_from_date']))
            #         operating_days_until_repair = days_diff(repair_cycle_row['repair_from_date'],previous_to_date if previous_to_date else part.date_of_installation)
            #         repair_cycle_row['operating_days_until_repair'] = operating_days_until_repair
                    
                    
                    
                    
            #         ###print('===== here is the dates differce ===')
            #         if len(spare_move_history_list) == i:
            #             pass
            #         else:
            #             continue
                
            #     elif (history.old_status == sent_for_repair_status and 
            #                     from_creation is not None and 
            #                     history.creation > from_creation):
            #         # #print('====================================================================================================')
            #         # #print('================== history entroy date =====',history.creation)
            #         # #print('==================  from_creation =====',from_creation)
                    
            #         # #print('====entered into the elif condition of old status ==',history.old_status)
            #         repair_cycle_row['repair_to_date'] = history.entry_date
            #         # operating_days_until_repair = days_diff(history.entry_date,(part.date_of_installation if repair_count == 1 else repair_cycle_row['repair_from_date']))
            #         # repair_cycle_row['operating_days_until_repair'] = operating_days_until_repair
            #         # #print('here ======== is the operating days ===',operating_days_until_repair)
            #         repair_cycle_row['repairing_time'] = days_diff(history.entry_date,repair_cycle_row['repair_from_date'])
            #         repair_cycle_row['from_to_history_doc'] = history.name
                    
            #         previous_to_date = history.entry_date

            #     if repair_cycle_row:
            #         # temp += 1
            #         # if temp == repair_count :
            #             data.append(repair_cycle_row)
            #             repair_cycle_row = {}
            repair_count = 0
            repair_cycle_row = {}
            last_repair_end_date = part.date_of_installation
            last_operation_end_date = None

            for i, history in enumerate(spare_move_history_list):

                # ---------------- DAMAGED ----------------
                if history.current_status == "Damaged":
                    # operation yahin ruk gaya
                    last_operation_end_date = history.entry_date
                    repair_cycle_row["damaged_marked_date"] = history.entry_date

                # ---------------- SENT FOR REPAIR ----------------
                elif history.current_status == sent_for_repair_status:
                    repair_count += 1

                    repair_cycle_row["repair_count"] = repair_count
                    repair_cycle_row["repair_from_date"] = history.entry_date
                    repair_cycle_row["service_request"] = history.service_request_reference
                    repair_cycle_row["po"] = history.repair_po_reference

                    # operating days = last operation end (Damaged) tak
                    repair_cycle_row["operating_days_until_repair"] = days_diff(
                        last_operation_end_date if last_operation_end_date else history.entry_date,
                        last_repair_end_date
                    )

                    # vendor
                    if history.repair_po_reference:
                        repair_cycle_row["repairing_vendor"] = frappe.db.get_value(
                            "Purchase Order",
                            history.repair_po_reference,
                            "supplier"
                        )

                    # repair abhi chal raha hai
                    repair_cycle_row["repairing_time"] = days_diff(
                        today(), history.entry_date
                    )

                # ---------------- REPAIR END ----------------
                elif (
                    history.old_status == sent_for_repair_status
                    and "repair_from_date" in repair_cycle_row
                ):
                    repair_cycle_row["repair_to_date"] = history.entry_date
                    repair_cycle_row["repairing_time"] = days_diff(
                        history.entry_date,
                        repair_cycle_row["repair_from_date"]
                    )

                    last_repair_end_date = history.entry_date

                    data.append(repair_cycle_row)
                    repair_cycle_row = {}

            # ---------------- FORCE APPEND OPEN / INCOMPLETE REPAIR CYCLE ----------------
            if repair_cycle_row:
                # agar repair start ho chuka hai par close nahi hua
                if "repair_from_date" in repair_cycle_row and "repair_to_date" not in repair_cycle_row:
                    repair_cycle_row["repairing_time"] = days_diff(
                        today(),
                        repair_cycle_row["repair_from_date"]
                    )

                data.append(repair_cycle_row)
                repair_cycle_row = {}



    
    
        
    if spare_report_type == consumable_spares_item_group:
        conditions = {}
        se_conditions = {}
        se_conditions['docstatus'] = 1
        se_conditions['stock_entry_type'] = spares_consumption_stock_entry_type
        # installation_from_date, installation_to_date = filters.get("date_range_of_installation") or [None, None]

        from_date, to_date = filters.get("entry_date") or [None, None]
        if from_date and from_date :
            se_conditions['posting_date'] = ["between",[from_date,to_date]]
        
        # Item group condition should be store spraes as well as consublable  so apply in condution in this statement
        
        conditions['item_group'] = ["in", [consumable_spares_item_group, store_spares_item_group]]
        

        # ###print('----------------------dispose========= ',dispose_from_date,dispose_to_date)
        # ###print('------================isntalllation == ',installation_from_date,installation_to_date)
        # ###print('this is the codnition of the date fo instlaltion -===',conditions)
        
        if filters.get('workstation'):
            conditions['custom_workstation'] = ['in' ,filters.get('workstation')]
            # item_group
        if filters.get('spare_part'):
            conditions['item_code'] = ['in' ,filters.get('spare_part') ]
            

        consumables_columns = [
            # {"fieldname":"id","label":"Id","fieldtype":"Link","options":"Stock Entry Detail","width":180},
            {"fieldname":"workstation","label":"Workstation","fieldtype":"Link","options":"Workstation","width":160},
            {"fieldname":"spare_part_name","label":"Spare Part Name","fieldtype":"Link","options":"Item","width":150},
            {"fieldname":"spare_part_code","label":"Spare Part Code","fieldtype":"Data","width":150},
            # Item gruop field
            {"fieldname":"item_group","label":"Item Group","fieldtype":"Data","width":150},
            
            # {"fieldname":"serial_no","label":"Serial No.","fieldtype":"Link","options":"Serial No","width":150},
            {"fieldname":"spare_qty","label":"Spare Qty","fieldtype":"Float","width":100},
            {"fieldname":"consumption_date","label":"Consumption Date","fieldtype":"Date","width":160},
            # {"fieldname":"dispose_replacement_date","label":"Dispose/Replacement Date","fieldtype":"Date","width":160},
            # {"fieldname":"service_life_days_this_workstation","label":"Service Life (Days)","fieldtype":"Data","width":160},
            # {"fieldname":"spare_status","label":"Status","fieldtype":"Char","width":160},
        ]
        
        all_stock_entries_with_consumable_spare_type = frappe.get_all("Stock Entry",filters=se_conditions,fields=['name'])
        
        # ##print('===================',all_stock_entries_with_consumable_spare_type)
        if not all_stock_entries_with_consumable_spare_type:
            frappe.throw(f"No Stock Entry Found with {spares_consumption_stock_entry_type} stock entry type.")
        
        
        else:
            se_names_arr = []
            for se in all_stock_entries_with_consumable_spare_type :
                se_names_arr.append(se.name)
                
            if se_names_arr:
                conditions['parent'] = ["in",se_names_arr]
            all_consumables_spares_stock_lines = frappe.get_all("Stock Entry Detail",filters=conditions,
                                                fields=[
                                                        "name","custom_workstation", "item_code", "creation","item_name","item_group",
                                                        "modified",
                                                        "qty"
                                                        ])
            if all_consumables_spares_stock_lines:
                total_records = len(all_consumables_spares_stock_lines)
            # #print('============== her is hte all recoreds - ', total_records)


            for line in all_consumables_spares_stock_lines:
                
                
                data.append({
                    # "id": line.name,                  
                    "workstation": line.custom_workstation,                  
                    "spare_part_name": line.item_name, 
                    "spare_part_code": line.item_code, 
                    "item_group": line.item_group,
                    "spare_qty" : line.qty,
                    "consumption_date": line.creation, 
                    # "dispose_replacement_date":line.dispose_replacement_date,
                    # "service_life_days":line.service_life_days if line.service_life_days > 0.0 else "-",
                    # "spare_status":line.spare_status,
                    # "serial_no":line.item_serial_number
                })
            # #print('============== her is hte all recoreds - ', total_records)
            # data.append({{"total_records": total_records}})
            return consumables_columns,data, {"total_records": total_records}
    
    elif spare_report_type == repairable_spares_item_group:
        # #print('============== her is hte all recoreds - ', total_records)
        
        return repairables_columns, data, {"total_records": total_records}

    else:
        return ""