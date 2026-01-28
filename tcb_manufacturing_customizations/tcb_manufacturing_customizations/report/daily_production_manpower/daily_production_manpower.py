import datetime
import frappe

def execute(filters=None):
    filters = filters or {}
    date_today = datetime.datetime.strptime(filters.get("date"), "%Y-%m-%d")

    columns = [
        {"fieldname": "department", "label": "Department", "fieldtype": "Link", "options": "Workstation", "width": 190},
        {"fieldname": "item_name", "label": "Item Name", "fieldtype": "Data", "width": 250},
        {"fieldname": "uom", "label": "UOM", "fieldtype": "Link", "options": "UOM", "width": 120},
        {"fieldname": "prod_today", "label": "Today", "fieldtype": "Float", "width": 150},
        {"fieldname": "prod_month", "label": "Prod. for Month", "fieldtype": "Float", "width": 190},
        {"fieldname": "prod_year", "label": "Prod. for Year", "fieldtype": "Float", "width": 190},
        {"fieldname": "manpower", "label": "Manpower Today", "fieldtype": "Int", "width": 190},
        {"fieldname": "month_manpower", "label": "Manpower Month", "fieldtype": "Int", "width": 190},
        {"fieldname": "year_manpower", "label": "Manpower Year", "fieldtype": "Int", "width": 190},
    ]

    daily_data = {}
    monthly_summary = {}
    yearly_summary = {}

    # -----------------------------
    # 1️⃣ DAILY DATA
    # -----------------------------
    s_entries = frappe.db.get_all(
        "Stock Entry",
        filters={
            "docstatus": 1,
            "custom_job_card_reference": ["!=", ""],
            "posting_date": filters.get("date")
        },
        fields=["custom_job_card_reference", "fg_completed_qty", "process_loss_qty"]
    )

    for entry in s_entries:
        jc = frappe.get_doc("Job Card", entry.custom_job_card_reference)
        if not jc:
            continue

        item_uom = frappe.db.get_value("Item",{"name":jc.production_item},"stock_uom")
        qty = entry.fg_completed_qty - entry.process_loss_qty
        emp_logs = frappe.db.get_all("Job Card Time Log", filters={"parent": jc.name}, pluck="employee")
        emp_count = len(set([e for e in emp_logs if e and str(e).strip()]))

        key = f"{jc.workstation}-{jc.item_name}"
        if key not in daily_data:
            daily_data[key] = {
                "Dept": jc.workstation,
                "Item": jc.item_name,
                "UOM": item_uom,
                "Today": 0,
                "TodayEmp": 0
            }

        daily_data[key]["Today"] += qty
        daily_data[key]["TodayEmp"] += emp_count

    # -----------------------------
    # 2️⃣ MONTHLY DATA (Dept-wise)
    # -----------------------------
    monthly_entries = frappe.db.get_all(
        "Stock Entry",
        filters={
            "docstatus": 1,
            "custom_job_card_reference": ["!=", ""],
            "posting_date": ["between", [f"{date_today.year}-{date_today.month:02d}-01", filters.get("date")]]
        },
        fields=["custom_job_card_reference", "fg_completed_qty", "process_loss_qty"]
    )

    for se in monthly_entries:
        jc = frappe.get_doc("Job Card", se.custom_job_card_reference)
        if not jc:
            continue

        item_uom = frappe.db.get_value("Item",{"name":jc.production_item},"stock_uom")
        qty = se.fg_completed_qty - se.process_loss_qty
        emp_logs = frappe.db.get_all("Job Card Time Log", filters={"parent": jc.name}, pluck="employee")
        emp_count = len(set([e for e in emp_logs if e and str(e).strip()]))

        if jc.workstation not in monthly_summary:
            monthly_summary[jc.workstation] = {"qty": 0, "emp": 0}
        monthly_summary[jc.workstation]["qty"] += qty
        monthly_summary[jc.workstation]["emp"] += emp_count

    # -----------------------------
    # 3️⃣ YEARLY DATA (Dept-wise)
    # -----------------------------
    yearly_entries = frappe.db.get_all(
        "Stock Entry",
        filters={
            "docstatus": 1,
            "custom_job_card_reference": ["!=", ""],
            "posting_date": ["between", [f"{date_today.year}-01-01", filters.get("date")]]
        },
        fields=["custom_job_card_reference", "fg_completed_qty", "process_loss_qty"]
    )

    for se in yearly_entries:
        jc = frappe.get_doc("Job Card", se.custom_job_card_reference)
        if not jc:
            continue
        
        item_uom = frappe.db.get_value("Item",{"name":jc.production_item},"stock_uom")
        qty = se.fg_completed_qty - se.process_loss_qty
        emp_logs = frappe.db.get_all("Job Card Time Log", filters={"parent": jc.name}, pluck="employee")
        emp_count = len(set([e for e in emp_logs if e and str(e).strip()]))

        if jc.workstation not in yearly_summary:
            yearly_summary[jc.workstation] = {"qty": 0, "emp": 0}
        yearly_summary[jc.workstation]["qty"] += qty
        yearly_summary[jc.workstation]["emp"] += emp_count

    # -----------------------------
    # 4️⃣ COMBINE ALL (show even if Today missing)
    # -----------------------------
    data = []
    all_departments = set(list(monthly_summary.keys()) + list(yearly_summary.keys()) +
                          [v["Dept"] for v in daily_data.values()])

    for dept_name in all_departments:
        # list all items if present in daily data, else empty item row
        dept_items = [v for v in daily_data.values() if v["Dept"] == dept_name]

        if dept_items:
            for vals in dept_items:
                data.append({
                    "department": vals["Dept"],
                    "item_name": vals["Item"],
                    "uom": vals["UOM"],
                    "prod_today": vals.get("Today", 0),
                    "prod_month": monthly_summary.get(vals["Dept"], {}).get("qty", 0),
                    "prod_year": yearly_summary.get(vals["Dept"], {}).get("qty", 0),
                    "manpower": vals.get("TodayEmp", 0),
                    "month_manpower": monthly_summary.get(vals["Dept"], {}).get("emp", 0),
                    "year_manpower": yearly_summary.get(vals["Dept"], {}).get("emp", 0),
                })
                
                
                
        else:
            # Department has no today data, but exists in month/year
            data.append({
                "department": dept_name,
                "item_name": "",
                "uom": item_uom,
                "prod_today": 0,
                "prod_month": monthly_summary.get(dept_name, {}).get("qty", 0),
                "prod_year": yearly_summary.get(dept_name, {}).get("qty", 0),
                "manpower": 0,
                "month_manpower": monthly_summary.get(dept_name, {}).get("emp", 0),
                "year_manpower": yearly_summary.get(dept_name, {}).get("emp", 0),
            })

    data.append({
                "department":"",
                "item_name": "",
                "uom": "",
                "prod_today": 0,
                "prod_month": 0,
                "prod_year": 0,
                "manpower": 0,
                "month_manpower": 0,
                "year_manpower":0,
            })
    
    
    
    attendances = frappe.db.get_all("Attendance",
                                   filters= {"attendance_date":filters.get("date")},
                                   fields = ["status","employee"])
    
    monthly_attendance = frappe.db.get_all("Attendance",
                                   filters= {"attendance_date":["between", [f"{date_today.year}-{date_today.month:02d}-01", filters.get("date")]]},
                                   fields = ["status","employee"])
    
    yearly_attendance = frappe.db.get_all("Attendance",
                                   filters= {"attendance_date":["between", [f"{date_today.year}-01-01", filters.get("date")]]},
                                   fields = ["status","employee"])
    
    
    stores = 0
    cleaning = 0
    admin = 0
    
    y_stores = 0
    y_cleaning = 0
    y_admin = 0
    
    m_stores = 0
    m_cleaning = 0
    m_admin = 0
    
    for attendance in attendances:
        if attendance.status=="Present":
            dept = frappe.db.get_value("Employee",attendance.employee,"department",as_dict=True)
            
            if dept.department == "Stores - APUI":
                stores +=1
            elif dept.department=="Administration - APUI":
                admin +=1
            elif dept.department == "Cleaning - APUI":
                cleaning+=1
                
                
    for attendance in monthly_attendance:
        if attendance.status=="Present":
            dept = frappe.db.get_value("Employee",attendance.employee,"department",as_dict=True)
            
            if dept.department == "Stores - APUI":
                m_stores +=1
            elif dept.department=="Administration - APUI":
                m_admin +=1
            elif dept.department == "Cleaning - APUI":
                m_cleaning+=1
                
                
    for attendance in yearly_attendance:
        if attendance.status=="Present":
            dept = frappe.db.get_value("Employee",attendance.employee,"department",as_dict=True)
            
            if dept.department == "Stores - APUI":
                y_stores +=1
            elif dept.department=="Administration - APUI":
                y_admin +=1
            elif dept.department == "Cleaning - APUI":
                y_cleaning+=1
    
         
    data.append({
                "department":"Stores",
                "item_name": "",
                "uom": "",
                "prod_today": 0,
                "prod_month": 0,
                "prod_year": 0,
                "manpower": stores,
                "month_manpower": m_stores,
                "year_manpower":y_stores,
            })
    data.append({
                "department":"Cleaning",
                "item_name": "",
                "uom": "",
                "prod_today": 0,
                "prod_month": 0,
                "prod_year": 0,
                "manpower": cleaning,
                "month_manpower": m_cleaning,
                "year_manpower":y_cleaning,
            })
    data.append({
                "department":"Administration",
                "item_name": "",
                "uom": "",
                "prod_today": 0,
                "prod_month": 0,
                "prod_year": 0,
                "manpower": admin,
                "month_manpower": m_admin,
                "year_manpower":y_admin,
            })
    return columns, data