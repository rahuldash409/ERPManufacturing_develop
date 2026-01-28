# Copyright (c) 2025, TCB Infotech Private Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime
import calendar


def execute(filters=None):
    filters = filters or {}
    frappe.db.set_value("Report","Production Master","prepared_report",0)
    columns = []
    data = []
    
    
    
    
    
    # ----------DAILY PRODUCTION -----------------------------DAILY PRODUCTION-------------------------------DAILY PRODUCTION
    
    
    if filters.get("department")=="Printing" and filters.get("specific_dept")=="Production":
        columns = [
            {"label":"Date","fieldname":"date","fieldtype":"Date","width":120},
            {"label":"Machine (Workstation)","fieldname":"machine","fieldtype":"Link","options":"Workstation","width":150},
            {"label":"Material","fieldname":"material","fieldtype":"Link","options":"Item","width":200},
            {"label":"Material Description","fieldname":"material_description","fieldtype":"Data","width":240},
            {"label":"Designed Capacity","fieldname":"designed_capacity","fieldtype":"Data","width":150},
            {"label":"UOM","fieldname":"uom","fieldtype":"Link","options":"UOM","width":100},
            {"label":"Shift A","fieldname":"production","fieldtype":"Data","width":160},
            {"label":"Efficiency","fieldname":"efficiency","fieldtype":"Percent","width":100},
            {"label":"Total","fieldname":"total","fieldtype":"Float","width":160},
            {"label":"Production To Date","fieldname":"production_to_date","fieldtype":"Float","width":160},
            {"label":"Production By Month","fieldname":"production_by_month","fieldtype":"Float","width":160},
            {"label":"Production By Year","fieldname":"production_by_year","fieldtype":"Float","width":160},
        ]

        monthly = {}  # Format: {workstation: {month_key: total_qty}}
        yearly = {}   # Format: {workstation: {year: total_qty}}
        cumulative = {}

        job_cards = frappe.db.get_all(
        "Job Card",
        filters={
            "status": "Completed",
            "custom_stock_entry_reference": ["!=", ""],
            "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
            "operation":"Printing"
        },
        fields=["workstation","operation","bom_no","posting_date","custom_shift","total_completed_qty","production_item","item_name"],
        order_by="posting_date asc"
        )

        # Get to_date for year calculation
        to_date = filters.get("to_date")
        if isinstance(to_date, str):
            to_date = datetime.strptime(to_date, "%Y-%m-%d")

        # Identify unique months and years we need to calculate for
        months_to_calculate = set()
        years_to_calculate = set()
        workstations = set()

        for jc in job_cards:
            workstations.add(jc.workstation)
            posting_date = jc.posting_date
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")

            month_key = posting_date.strftime("%Y-%m")
            year_key = str(posting_date.year)

            months_to_calculate.add((jc.workstation, month_key))
            years_to_calculate.add((jc.workstation, year_key))

        # Calculate full month totals (entire month, not just filtered range)
        for workstation, month_key in months_to_calculate:
            year, month = month_key.split("-")

            last_day = calendar.monthrange(int(year), int(month))[1]
            
            

            # Get all production for this entire month
            month_job_cards = frappe.db.get_all(
                "Job Card",
                filters={
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "workstation": workstation,
                    "operation": "Printing",
                    "posting_date": ["between", [f"{year}-{month}-01", f"{year}-{month}-{last_day}"]]
                },
                fields=["total_completed_qty"]
            )

            if workstation not in monthly:
                monthly[workstation] = {}

            monthly[workstation][month_key] = sum([jc.total_completed_qty for jc in month_job_cards])

        # Calculate year-to-date totals (Jan 1 to to_date for each year)
        for workstation, year_key in years_to_calculate:
            # Get year start and the minimum of (year end, to_date)
            year_start = f"{year_key}-01-01"
            year_end_date = datetime(int(year_key), 12, 31)

            # Use to_date if it's in the same year, otherwise use year end
            if to_date.year == int(year_key):
                query_end_date = to_date.strftime("%Y-%m-%d")
            else:
                query_end_date = year_end_date.strftime("%Y-%m-%d")

            # Get all production from Jan 1 to to_date (or year end)
            year_job_cards = frappe.db.get_all(
                "Job Card",
                filters={
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "workstation": workstation,
                    "operation": "Printing",
                    "posting_date": ["between", [year_start, query_end_date]]
                },
                fields=["total_completed_qty"]
            )

            if workstation not in yearly:
                yearly[workstation] = {}

            yearly[workstation][year_key] = sum([jc.total_completed_qty for jc in year_job_cards])

        # Build rows with pre-calculated totals
        for jc in job_cards:
            job_capacity = frappe.db.get_value("Workstation", jc.workstation, "custom_job_capacity")
            uom = frappe.db.get_value("Item", jc.production_item, "stock_uom")

            # Convert posting_date to datetime if it's a string
            posting_date = jc.posting_date
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")

            # Extract month and year
            month_key = posting_date.strftime("%Y-%m")
            year_key = str(posting_date.year)

            # Initialize cumulative tracking
            if jc.workstation not in cumulative:
                cumulative[jc.workstation] = 0
            cumulative[jc.workstation] += jc.total_completed_qty

            rows = {
                "date": jc.posting_date,
                "machine": jc.workstation,
                "material": jc.production_item,
                "material_description": jc.item_name,
                "designed_capacity": job_capacity,
                "uom": uom,
                "production": jc.total_completed_qty,
                "efficiency": (jc.total_completed_qty/job_capacity)*100 if job_capacity else 0,
                "total": jc.total_completed_qty,
                "production_to_date": cumulative[jc.workstation],
                "production_by_month": monthly.get(jc.workstation, {}).get(month_key, 0),
                "production_by_year": yearly.get(jc.workstation, {}).get(year_key, 0)
            }
            data.append(rows)


            
            
    if filters.get("department")=="Segregation" and filters.get("specific_dept")=="Production":
        columns = [
        {"label":"Date","fieldname":"date","fieldtype":"Date","width":120},
        {"label":"Machine (Workstation)","fieldname":"machine","fieldtype":"Link","options":"Workstation","width":150},
        {"label":"Material","fieldname":"material","fieldtype":"Link","options":"Item","width":200},
        {"label":"Material Description","fieldname":"material_description","fieldtype":"Data","width":240},
        {"label":"Designed Capacity","fieldname":"designed_capacity","fieldtype":"Data","width":150},
        {"label":"UOM","fieldname":"uom","fieldtype":"Link","options":"UOM","width":100},
        {"label":"Shift A","fieldname":"production","fieldtype":"Data","width":160},
        {"label":"Efficiency","fieldname":"efficiency","fieldtype":"Percent","width":100},
        {"label":"Total","fieldname":"total","fieldtype":"Float","width":160},
        {"label":"Production To Date","fieldname":"production_to_date","fieldtype":"Float","width":160},
        {"label":"Production By Month","fieldname":"production_by_month","fieldtype":"Float","width":160},
        {"label":"Production By Year","fieldname":"production_by_year","fieldtype":"Float","width":160},
        ]
        
        monthly = {}  # Format: {workstation: {month_key: total_qty}}
        yearly = {}   # Format: {workstation: {year: total_qty}}  
        rows = {}
        cumulative = {}
        job_cards = frappe.db.get_all(
        "Job Card",
        filters={
            "status": "Completed",
            "custom_stock_entry_reference": ["!=", ""],
            "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
            "operation":"Segregation"
        },
        fields=["workstation","operation","bom_no","posting_date","custom_shift","total_completed_qty","production_item","item_name"],
        order_by="posting_date asc"
        )

        # Get to_date for year calculation
        to_date = filters.get("to_date")
        if isinstance(to_date, str):
            to_date = datetime.strptime(to_date, "%Y-%m-%d")

        # Identify unique months and years we need to calculate for
        months_to_calculate = set()
        years_to_calculate = set()
        workstations = set()

        for jc in job_cards:
            workstations.add(jc.workstation)
            posting_date = jc.posting_date
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")

            month_key = posting_date.strftime("%Y-%m")
            year_key = str(posting_date.year)

            months_to_calculate.add((jc.workstation, month_key))
            years_to_calculate.add((jc.workstation, year_key))

        # Calculate full month totals (entire month, not just filtered range)
        for workstation, month_key in months_to_calculate:
            year, month = month_key.split("-")

            last_day = calendar.monthrange(int(year), int(month))[1]

            # Get all production for this entire month
            month_job_cards = frappe.db.get_all(
                "Job Card",
                filters={
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "workstation": workstation,
                    "operation": "Segregation",
                    "posting_date": ["between", [f"{year}-{month}-01", f"{year}-{month}-{last_day}"]]
                },
                fields=["total_completed_qty"]
            )

            if workstation not in monthly:
                monthly[workstation] = {}

            monthly[workstation][month_key] = sum([jc.total_completed_qty for jc in month_job_cards])

        # Calculate year-to-date totals (Jan 1 to to_date for each year)
        for workstation, year_key in years_to_calculate:
            # Get year start and the minimum of (year end, to_date)
            year_start = f"{year_key}-01-01"
            year_end_date = datetime(int(year_key), 12, 31)

            # Use to_date if it's in the same year, otherwise use year end
            if to_date.year == int(year_key):
                query_end_date = to_date.strftime("%Y-%m-%d")
            else:
                query_end_date = year_end_date.strftime("%Y-%m-%d")

            # Get all production from Jan 1 to to_date (or year end)
            year_job_cards = frappe.db.get_all(
                "Job Card",
                filters={
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "workstation": workstation,
                    "operation": "Segregation",
                    "posting_date": ["between", [year_start, query_end_date]]
                },
                fields=["total_completed_qty"]
            )

            if workstation not in yearly:
                yearly[workstation] = {}

            yearly[workstation][year_key] = sum([jc.total_completed_qty for jc in year_job_cards])

        # Build rows with pre-calculated totals
        for jc in job_cards:
            job_capacity = frappe.db.get_value("Workstation", jc.workstation, "custom_job_capacity")
            uom = frappe.db.get_value("Item", jc.production_item, "stock_uom")

            # Convert posting_date to datetime if it's a string
            posting_date = jc.posting_date
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")

            # Extract month and year
            month_key = posting_date.strftime("%Y-%m")
            year_key = str(posting_date.year)

            # Initialize cumulative tracking
            if jc.workstation not in cumulative:
                cumulative[jc.workstation] = 0
            cumulative[jc.workstation] += jc.total_completed_qty

            rows = {
                "date": jc.posting_date,
                "machine": jc.workstation,
                "material": jc.production_item,
                "material_description": jc.item_name,
                "designed_capacity": job_capacity,
                "uom": uom,
                "production": jc.total_completed_qty,
                "efficiency": (jc.total_completed_qty/job_capacity)*100 if job_capacity else 0,
                "total": jc.total_completed_qty,
                "production_to_date": cumulative[jc.workstation],
                "production_by_month": monthly.get(jc.workstation, {}).get(month_key, 0),
                "production_by_year": yearly.get(jc.workstation, {}).get(year_key, 0)
            }
            data.append(rows)





    
    if filters.get("department")=="Slitting" and filters.get("specific_dept")=="Production":
        columns = [
        {"label":"Date","fieldname":"date","fieldtype":"Date","width":120},
        {"label":"Machine (Workstation)","fieldname":"machine","fieldtype":"Link","options":"Workstation","width":150},
        {"label":"Material","fieldname":"material","fieldtype":"Link","options":"Item","width":200},
        {"label":"Material Description","fieldname":"material_description","fieldtype":"Data","width":240},
        {"label":"Designed Capacity","fieldname":"designed_capacity","fieldtype":"Data","width":150},
        {"label":"UOM","fieldname":"uom","fieldtype":"Link","options":"UOM","width":100},
        {"label":"Shift A","fieldname":"production","fieldtype":"Data","width":160},
        {"label":"Efficiency","fieldname":"efficiency","fieldtype":"Percent","width":100},
        {"label":"Total","fieldname":"total","fieldtype":"Float","width":160},
        {"label":"Production To Date","fieldname":"production_to_date","fieldtype":"Float","width":160},
        {"label":"Production By Month","fieldname":"production_by_month","fieldtype":"Float","width":160},
        {"label":"Production By Year","fieldname":"production_by_year","fieldtype":"Float","width":160},
        ]
            
        rows = {}
        monthly = {}  # Format: {workstation: {month_key: total_qty}}
        yearly = {}   # Format: {workstation: {year: total_qty}}
        cumulative = {}

        job_cards = frappe.db.get_all(
        "Job Card",
        filters={
            "status": "Completed",
            "custom_stock_entry_reference": ["!=", ""],
            "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
            "operation":"Slitting"
        },
        fields=["workstation","operation","bom_no","posting_date","custom_shift","total_completed_qty","production_item","item_name"],
        order_by="posting_date asc"
        )

        # Get to_date for year calculation
        to_date = filters.get("to_date")
        if isinstance(to_date, str):
            to_date = datetime.strptime(to_date, "%Y-%m-%d")

        # Identify unique months and years we need to calculate for
        months_to_calculate = set()
        years_to_calculate = set()
        workstations = set()

        for jc in job_cards:
            workstations.add(jc.workstation)
            posting_date = jc.posting_date
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")

            month_key = posting_date.strftime("%Y-%m")
            year_key = str(posting_date.year)

            months_to_calculate.add((jc.workstation, month_key))
            years_to_calculate.add((jc.workstation, year_key))

        # Calculate full month totals (entire month, not just filtered range)
        for workstation, month_key in months_to_calculate:
            year, month = month_key.split("-")

            last_day = calendar.monthrange(int(year), int(month))[1]

            # Get all production for this entire month
            month_job_cards = frappe.db.get_all(
                "Job Card",
                filters={
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "workstation": workstation,
                    "operation": "Slitting",
                    "posting_date": ["between", [f"{year}-{month}-01", f"{year}-{month}-{last_day}"]]
                },
                fields=["total_completed_qty"]
            )

            if workstation not in monthly:
                monthly[workstation] = {}

            monthly[workstation][month_key] = sum([jc.total_completed_qty for jc in month_job_cards])

        # Calculate year-to-date totals (Jan 1 to to_date for each year)
        for workstation, year_key in years_to_calculate:
            # Get year start and the minimum of (year end, to_date)
            year_start = f"{year_key}-01-01"
            year_end_date = datetime(int(year_key), 12, 31)

            # Use to_date if it's in the same year, otherwise use year end
            if to_date.year == int(year_key):
                query_end_date = to_date.strftime("%Y-%m-%d")
            else:
                query_end_date = year_end_date.strftime("%Y-%m-%d")

            # Get all production from Jan 1 to to_date (or year end)
            year_job_cards = frappe.db.get_all(
                "Job Card",
                filters={
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "workstation": workstation,
                    "operation": "Slitting",
                    "posting_date": ["between", [year_start, query_end_date]]
                },
                fields=["total_completed_qty"]
            )

            if workstation not in yearly:
                yearly[workstation] = {}

            yearly[workstation][year_key] = sum([jc.total_completed_qty for jc in year_job_cards])

        # Build rows with pre-calculated totals
        for jc in job_cards:
            job_capacity = frappe.db.get_value("Workstation", jc.workstation, "custom_job_capacity")
            uom = frappe.db.get_value("Item", jc.production_item, "stock_uom")

            # Convert posting_date to datetime if it's a string
            posting_date = jc.posting_date
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")

            # Extract month and year
            month_key = posting_date.strftime("%Y-%m")
            year_key = str(posting_date.year)

            # Initialize cumulative tracking
            if jc.workstation not in cumulative:
                cumulative[jc.workstation] = 0
            cumulative[jc.workstation] += jc.total_completed_qty

            rows = {
                "date": jc.posting_date,
                "machine": jc.workstation,
                "material": jc.production_item,
                "material_description": jc.item_name,
                "designed_capacity": job_capacity,
                "uom": uom,
                "production": jc.total_completed_qty,
                "efficiency": (jc.total_completed_qty/job_capacity)*100 if job_capacity else 0,
                "total": jc.total_completed_qty,
                "production_to_date": cumulative[jc.workstation],
                "production_by_month": monthly.get(jc.workstation, {}).get(month_key, 0),
                "production_by_year": yearly.get(jc.workstation, {}).get(year_key, 0)
            }
            data.append(rows)



    if filters.get("department")=="AD*STARKON" and filters.get("specific_dept")=="Production":
        columns = [
        {"label":"Date","fieldname":"date","fieldtype":"Date","width":120},
        {"label":"Machine (Workstation)","fieldname":"machine","fieldtype":"Link","options":"Workstation","width":150},
        {"label":"Material","fieldname":"material","fieldtype":"Link","options":"Item","width":200},
        {"label":"Material Description","fieldname":"material_description","fieldtype":"Data","width":240},
        {"label":"Designed Capacity","fieldname":"designed_capacity","fieldtype":"Data","width":150},
        {"label":"UOM","fieldname":"uom","fieldtype":"Link","options":"UOM","width":100},
        {"label":"Shift A","fieldname":"production","fieldtype":"Data","width":160},
        {"label":"Efficiency","fieldname":"efficiency","fieldtype":"Percent","width":100},
        {"label":"Total","fieldname":"total","fieldtype":"Float","width":160},
        {"label":"Production To Date","fieldname":"production_to_date","fieldtype":"Float","width":160},
        {"label":"Production By Month","fieldname":"production_by_month","fieldtype":"Float","width":160},
        {"label":"Production By Year","fieldname":"production_by_year","fieldtype":"Float","width":160},
        ]
            
        rows = {}
        monthly = {}  # Format: {workstation: {month_key: total_qty}}
        yearly = {}   # Format: {workstation: {year: total_qty}}
        cumulative = {}

        job_cards = frappe.db.get_all(
        "Job Card",
        filters={
            "status": "Completed",
            "custom_stock_entry_reference": ["!=", ""],
            "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
            "operation":"Bag Manufacturing"
        },
        fields=["workstation","operation","bom_no","posting_date","custom_shift","total_completed_qty","production_item","item_name"],
        order_by="posting_date asc"
        )

        # Get to_date for year calculation
        to_date = filters.get("to_date")
        if isinstance(to_date, str):
            to_date = datetime.strptime(to_date, "%Y-%m-%d")

        # Identify unique months and years we need to calculate for
        months_to_calculate = set()
        years_to_calculate = set()
        workstations = set()

        for jc in job_cards:
            workstations.add(jc.workstation)
            posting_date = jc.posting_date
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")

            month_key = posting_date.strftime("%Y-%m")
            year_key = str(posting_date.year)

            months_to_calculate.add((jc.workstation, month_key))
            years_to_calculate.add((jc.workstation, year_key))

        # Calculate full month totals (entire month, not just filtered range)
        for workstation, month_key in months_to_calculate:
            year, month = month_key.split("-")

            last_day = calendar.monthrange(int(year), int(month))[1]

            # Get all production for this entire month
            month_job_cards = frappe.db.get_all(
                "Job Card",
                filters={
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "workstation": workstation,
                    "operation": "Bag Manufacturing",
                    "posting_date": ["between", [f"{year}-{month}-01", f"{year}-{month}-{last_day}"]]
                },
                fields=["total_completed_qty"]
            )

            if workstation not in monthly:
                monthly[workstation] = {}

            monthly[workstation][month_key] = sum([jc.total_completed_qty for jc in month_job_cards])

        # Calculate year-to-date totals (Jan 1 to to_date for each year)
        for workstation, year_key in years_to_calculate:
            # Get year start and the minimum of (year end, to_date)
            year_start = f"{year_key}-01-01"
            year_end_date = datetime(int(year_key), 12, 31)

            # Use to_date if it's in the same year, otherwise use year end
            if to_date.year == int(year_key):
                query_end_date = to_date.strftime("%Y-%m-%d")
            else:
                query_end_date = year_end_date.strftime("%Y-%m-%d")

            # Get all production from Jan 1 to to_date (or year end)
            year_job_cards = frappe.db.get_all(
                "Job Card",
                filters={
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "workstation": workstation,
                    "operation": "Bag Manufacturing",
                    "posting_date": ["between", [year_start, query_end_date]]
                },
                fields=["total_completed_qty"]
            )

            if workstation not in yearly:
                yearly[workstation] = {}

            yearly[workstation][year_key] = sum([jc.total_completed_qty for jc in year_job_cards])

        # Build rows with pre-calculated totals
        for jc in job_cards:
            job_capacity = frappe.db.get_value("Workstation", jc.workstation, "custom_job_capacity")
            uom = frappe.db.get_value("Item", jc.production_item, "stock_uom")

            # Convert posting_date to datetime if it's a string
            posting_date = jc.posting_date
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")

            # Extract month and year
            month_key = posting_date.strftime("%Y-%m")
            year_key = str(posting_date.year)

            # Initialize cumulative tracking
            if jc.workstation not in cumulative:
                cumulative[jc.workstation] = 0
            cumulative[jc.workstation] += jc.total_completed_qty

            rows = {
                "date": jc.posting_date,
                "machine": jc.workstation,
                "material": jc.production_item,
                "material_description": jc.item_name,
                "designed_capacity": job_capacity,
                "uom": uom,
                "production": jc.total_completed_qty,
                "efficiency": (jc.total_completed_qty/job_capacity)*100 if job_capacity else 0,
                "total": jc.total_completed_qty,
                "production_to_date": cumulative[jc.workstation],
                "production_by_month": monthly.get(jc.workstation, {}).get(month_key, 0),
                "production_by_year": yearly.get(jc.workstation, {}).get(year_key, 0)
            }
            data.append(rows)


    
    if filters.get("department")=="Packaging" and filters.get("specific_dept")=="Production":
        columns = [
        {"label":"Date","fieldname":"date","fieldtype":"Date","width":120},
        {"label":"Machine (Workstation)","fieldname":"machine","fieldtype":"Link","options":"Workstation","width":150},
        {"label":"Material","fieldname":"material","fieldtype":"Link","options":"Item","width":200},
        {"label":"Material Description","fieldname":"material_description","fieldtype":"Data","width":240},
        {"label":"Designed Capacity","fieldname":"designed_capacity","fieldtype":"Data","width":150},
        {"label":"UOM","fieldname":"uom","fieldtype":"Link","options":"UOM","width":100},
        {"label":"Shift A","fieldname":"production","fieldtype":"Data","width":160},
        {"label":"Efficiency","fieldname":"efficiency","fieldtype":"Percent","width":100},
        {"label":"Total","fieldname":"total","fieldtype":"Float","width":160},
        {"label":"Production To Date","fieldname":"production_to_date","fieldtype":"Float","width":160},
        {"label":"Production By Month","fieldname":"production_by_month","fieldtype":"Float","width":160},
        {"label":"Production By Year","fieldname":"production_by_year","fieldtype":"Float","width":160},
        ]
            
        rows = {}
        monthly = {}  # Format: {workstation: {month_key: total_qty}}
        yearly = {}   # Format: {workstation: {year: total_qty}}
        cumulative = {}

        job_cards = frappe.db.get_all(
        "Job Card",
        filters={
            "status": "Completed",
            "custom_stock_entry_reference": ["!=", ""],
            "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
            "operation":"Packaging"
        },
        fields=["workstation","operation","bom_no","posting_date","custom_shift","total_completed_qty","production_item","item_name"],
        order_by="posting_date asc"
        )
        
        # Get to_date for year calculation
        to_date = filters.get("to_date")
        if isinstance(to_date, str):
            to_date = datetime.strptime(to_date, "%Y-%m-%d")
        
        # Identify unique months and years we need to calculate for
        months_to_calculate = set()
        years_to_calculate = set()
        workstations = set()
        
        for jc in job_cards:
            workstations.add(jc.workstation)
            posting_date = jc.posting_date
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")
            
            month_key = posting_date.strftime("%Y-%m")
            year_key = str(posting_date.year)
            
            months_to_calculate.add((jc.workstation, month_key))
            years_to_calculate.add((jc.workstation, year_key))
        
        # Calculate full month totals (entire month, not just filtered range)
        for workstation, month_key in months_to_calculate:
            year, month = month_key.split("-")

            last_day = calendar.monthrange(int(year), int(month))[1]
            
            # Get all production for this entire month
            month_job_cards = frappe.db.get_all(
                "Job Card",
                filters={
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "workstation": workstation,
                    "operation": "Packaging",
                    "posting_date": ["between", [f"{year}-{month}-01", f"{year}-{month}-{last_day}"]]
                },
                fields=["total_completed_qty"]
            )
            
            if workstation not in monthly:
                monthly[workstation] = {}
            
            monthly[workstation][month_key] = sum([jc.total_completed_qty for jc in month_job_cards])
        
        # Calculate year-to-date totals (Jan 1 to to_date for each year)
        for workstation, year_key in years_to_calculate:
            # Get year start and the minimum of (year end, to_date)
            year_start = f"{year_key}-01-01"
            year_end_date = datetime(int(year_key), 12, 31)
            
            last_day = calendar.monthrange(int(year), int(month))[1]
            
            # Use to_date if it's in the same year, otherwise use year end
            if to_date.year == int(year_key):
                query_end_date = to_date.strftime("%Y-%m-%d")
            else:
                query_end_date = year_end_date.strftime("%Y-%m-%d")
            
            # Get all production from Jan 1 to to_date (or year end)
            year_job_cards = frappe.db.get_all(
                "Job Card",
                filters={
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "workstation": workstation,
                    "operation": "Packaging",
                    "posting_date": ["between", [year_start, query_end_date]]
                },
                fields=["total_completed_qty"]
            )
            
            if workstation not in yearly:
                yearly[workstation] = {}
            
            yearly[workstation][year_key] = sum([jc.total_completed_qty for jc in year_job_cards])
        
        # Build rows with pre-calculated totals
        for jc in job_cards:
            job_capacity = frappe.db.get_value("Workstation", jc.workstation, "custom_job_capacity")
            uom = frappe.db.get_value("Item", jc.production_item, "stock_uom")
            
            # Convert posting_date to datetime if it's a string
            posting_date = jc.posting_date
            if isinstance(posting_date, str):
                posting_date = datetime.strptime(posting_date, "%Y-%m-%d")
            
            # Extract month and year
            month_key = posting_date.strftime("%Y-%m")
            year_key = str(posting_date.year)
            
            # Initialize cumulative tracking
            if jc.workstation not in cumulative:
                cumulative[jc.workstation] = 0
            cumulative[jc.workstation] += jc.total_completed_qty
            
            rows = {
                "date": jc.posting_date,
                "machine": jc.workstation,
                "material": jc.production_item,
                "material_description": jc.item_name,
                "designed_capacity": job_capacity,
                "uom": uom,
                "production": jc.total_completed_qty,
                "efficiency": (jc.total_completed_qty/job_capacity)*100 if job_capacity else 0,
                "total": jc.total_completed_qty,
                "production_to_date": cumulative[jc.workstation],
                "production_by_month": monthly.get(jc.workstation, {}).get(month_key, 0),
                "production_by_year": yearly.get(jc.workstation, {}).get(year_key, 0)
            }
            data.append(rows)
        
        
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    # DAILY POWER CONSUMPTION --------------------------DAILY POWER CONSUMPTION------------------DAILY POWER CONSUMPTION
    
    
    if filters.get("department")=="Printing" and filters.get("specific_dept")=="Power":
        columns =[
        {"fieldname":"date","label":"Date","fieldtype":"Date","width":150},
        {"fieldname":"workstation","label":"Workstation","fieldtype":"Link","options":"Workstation","width":160},
        # {"fieldname":"ipc_unit","label":"IPC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"ipc_prod","label":"IPC. Production","fieldtype":"Float","width":160},
        # {"fieldname":"ipc_cost","label":"IPC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"uom","label":"UOM","fieldtype":"Link","options":"UOM","width":160},
        {"fieldname":"today_apc_unit","label":"Today APC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"today_apc_prod","label":"Today APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"today_apc_cost","label":"Today APC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"apc_unit","label":"Todate APC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"apc_prod","label":"Todate APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"apc_cost","label":"Todate APC. Unit Cost","fieldtype":"Float","width":160},
        ]

        job_cards = frappe.db.get_all("Job Card",
                                      filters={
                                          "status":"Completed",
                                          "custom_stock_entry_reference":["!=",""],
                                          "posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],
                                          "operation":"Printing"
                                      },
                                      fields = ["production_item","workstation","total_completed_qty","posting_date"]
                                      )
        workstation={}

        for jc in job_cards:
            workstn = frappe.get_doc("Workstation",jc.workstation)
            units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jc.workstation},fields=["unit_consumption"],limit=1)
            itm = frappe.get_doc("Item",jc.production_item)
            if jc.workstation not in workstation:
                workstation[jc.workstation] = {
                    "date":jc.posting_date,
                    "workstation":jc.workstation,
                    # "ipc_unit":workstn.custom_ideal_unit_consumption,
                    # "ipc_prod":workstn.custom_ideal_production,
                    # "ipc_cost":workstn.custom_ideal_unit_cost,
                    "uom":f"Units/{itm.stock_uom}",
                    "today_apc_unit":0,
                    "today_apc_prod":0,
                    "today_apc_cost":0,
                    "apc_unit":0,
                    "apc_prod":0,
                    "apc_cost":0
                }
            workstation[jc.workstation]["today_apc_unit"] += units[0].get("unit_consumption") if units else 0
            workstation[jc.workstation]["today_apc_prod"] += jc.total_completed_qty

        todate_jc = frappe.db.get_all("Job Card",
                                      filters={
                                          "status":"Completed",
                                          "custom_stock_entry_reference":["!=",""],
                                          "posting_date":["<=",filters.get("to_date")],
                                          "operation":"Printing"
                                      },
                                      fields = ["production_item","workstation","total_completed_qty","posting_date"])
        for jcard in todate_jc:
            units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jcard.workstation},fields=["unit_consumption"],limit=1)

            if jcard.workstation in workstation:            
                workstation[jcard.workstation]["apc_unit"] += units[0].get("unit_consumption") if units else 0
                workstation[jcard.workstation]["apc_prod"] += jcard.total_completed_qty


        for wrkstn, vals in workstation.items():
            workstation[wrkstn]["today_apc_cost"] = vals["today_apc_unit"]/vals["today_apc_prod"] if vals["today_apc_prod"] else 0
            workstation[wrkstn]["apc_cost"] = vals["apc_unit"]/vals["apc_prod"] if vals["apc_prod"] else 0
            data.append(vals)
            
            
            
            
            
    if filters.get("department")=="Segregation" and filters.get("specific_dept")=="Power":
        columns =[
        {"fieldname":"date","label":"Date","fieldtype":"Date","width":150},
        {"fieldname":"workstation","label":"Workstation","fieldtype":"Link","options":"Workstation","width":160},
        # {"fieldname":"ipc_unit","label":"IPC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"ipc_prod","label":"IPC. Production","fieldtype":"Float","width":160},
        # {"fieldname":"ipc_cost","label":"IPC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"uom","label":"UOM","fieldtype":"Link","options":"UOM","width":160},
        {"fieldname":"today_apc_unit","label":"Today APC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"today_apc_prod","label":"Today APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"today_apc_cost","label":"Today APC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"apc_unit","label":"Todate APC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"apc_prod","label":"Todate APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"apc_cost","label":"Todate APC. Unit Cost","fieldtype":"Float","width":160},
        ]

        job_cards = frappe.db.get_all("Job Card",
                                      filters={
                                          "status":"Completed",
                                          "custom_stock_entry_reference":["!=",""],
                                          "posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],
                                          "operation":"Segregation"
                                      },
                                      fields = ["production_item","workstation","total_completed_qty","posting_date"]
                                      )
        workstation={}

        for jc in job_cards:
            workstn = frappe.get_doc("Workstation",jc.workstation)
            units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jc.workstation},fields=["unit_consumption"],limit=1)
            itm = frappe.get_doc("Item",jc.production_item)
            if jc.workstation not in workstation:
                workstation[jc.workstation] = {
                    "date":jc.posting_date,
                    "workstation":jc.workstation,
                    # "ipc_unit":workstn.custom_ideal_unit_consumption,
                    # "ipc_prod":workstn.custom_ideal_production,
                    # "ipc_cost":workstn.custom_ideal_unit_cost,
                    "uom":f"Units/{itm.stock_uom}",
                    "today_apc_unit":0,
                    "today_apc_prod":0,
                    "today_apc_cost":0,
                    "apc_unit":0,
                    "apc_prod":0,
                    "apc_cost":0
                }
            workstation[jc.workstation]["today_apc_unit"] += units[0].get("unit_consumption") if units else 0
            workstation[jc.workstation]["today_apc_prod"] += jc.total_completed_qty

        todate_jc = frappe.db.get_all("Job Card",
                                      filters={
                                          "status":"Completed",
                                          "custom_stock_entry_reference":["!=",""],
                                          "posting_date":["<=",filters.get("to_date")],
                                          "operation":"Segregation"
                                      },
                                      fields = ["production_item","workstation","total_completed_qty","posting_date"])
        for jcard in todate_jc:
            units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jcard.workstation},fields=["unit_consumption"],limit=1)

            if jcard.workstation in workstation:            
                workstation[jcard.workstation]["apc_unit"] += units[0].get("unit_consumption") if units else 0
                workstation[jcard.workstation]["apc_prod"] += jcard.total_completed_qty


        for wrkstn, vals in workstation.items():
            workstation[wrkstn]["today_apc_cost"] = vals["today_apc_unit"]/vals["today_apc_prod"] if vals["today_apc_prod"] else 0
            workstation[wrkstn]["apc_cost"] = vals["apc_unit"]/vals["apc_prod"] if vals["apc_prod"] else 0
            data.append(vals)        
            
            
            
            
            
            
            
    if filters.get("department")=="Slitting" and filters.get("specific_dept")=="Power":
        columns =[
        {"fieldname":"date","label":"Date","fieldtype":"Date","width":150},
        {"fieldname":"workstation","label":"Workstation","fieldtype":"Link","options":"Workstation","width":160},
        # {"fieldname":"ipc_unit","label":"IPC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"ipc_prod","label":"IPC. Production","fieldtype":"Float","width":160},
        # {"fieldname":"ipc_cost","label":"IPC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"uom","label":"UOM","fieldtype":"Link","options":"UOM","width":160},
        {"fieldname":"today_apc_unit","label":"Today APC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"today_apc_prod","label":"Today APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"today_apc_cost","label":"Today APC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"apc_unit","label":"Todate APC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"apc_prod","label":"Todate APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"apc_cost","label":"Todate APC. Unit Cost","fieldtype":"Float","width":160},
        ]

        job_cards = frappe.db.get_all("Job Card",
                                      filters={
                                          "status":"Completed",
                                          "custom_stock_entry_reference":["!=",""],
                                          "posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],
                                          "operation":"Slitting"
                                      },
                                      fields = ["production_item","workstation","total_completed_qty","posting_date"]
                                      )
        workstation={}

        for jc in job_cards:
            workstn = frappe.get_doc("Workstation",jc.workstation)
            units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jc.workstation},fields=["unit_consumption"],limit=1)
            itm = frappe.get_doc("Item",jc.production_item)
            if jc.workstation not in workstation:
                workstation[jc.workstation] = {
                    "date":jc.posting_date,
                    "workstation":jc.workstation,
                    # "ipc_unit":workstn.custom_ideal_unit_consumption,
                    # "ipc_prod":workstn.custom_ideal_production,
                    # "ipc_cost":workstn.custom_ideal_unit_cost,
                    "uom":f"Units/{itm.stock_uom}",
                    "today_apc_unit":0,
                    "today_apc_prod":0,
                    "today_apc_cost":0,
                    "apc_unit":0,
                    "apc_prod":0,
                    "apc_cost":0
                }
            workstation[jc.workstation]["today_apc_unit"] += units[0].get("unit_consumption") if units else 0
            workstation[jc.workstation]["today_apc_prod"] += jc.total_completed_qty

        todate_jc = frappe.db.get_all("Job Card",
                                      filters={
                                          "status":"Completed",
                                          "custom_stock_entry_reference":["!=",""],
                                          "posting_date":["<=",filters.get("to_date")],
                                          "operation":"Slitting"
                                      },
                                      fields = ["production_item","workstation","total_completed_qty","posting_date"])
        for jcard in todate_jc:
            units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jcard.workstation},fields=["unit_consumption"],limit=1)

            if jcard.workstation in workstation:            
                workstation[jcard.workstation]["apc_unit"] += units[0].get("unit_consumption") if units else 0
                workstation[jcard.workstation]["apc_prod"] += jcard.total_completed_qty


        for wrkstn, vals in workstation.items():
            workstation[wrkstn]["today_apc_cost"] = vals["today_apc_unit"]/vals["today_apc_prod"] if vals["today_apc_prod"] else 0
            workstation[wrkstn]["apc_cost"] = vals["apc_unit"]/vals["apc_prod"] if vals["apc_prod"] else 0
            data.append(vals)
            
            
            
            
    if filters.get("department")=="AD*STARKON" and filters.get("specific_dept")=="Power":
        columns =[
        {"fieldname":"date","label":"Date","fieldtype":"Date","width":150},
        {"fieldname":"workstation","label":"Workstation","fieldtype":"Link","options":"Workstation","width":160},
        # {"fieldname":"ipc_unit","label":"IPC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"ipc_prod","label":"IPC. Production","fieldtype":"Float","width":160},
        # {"fieldname":"ipc_cost","label":"IPC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"uom","label":"UOM","fieldtype":"Link","options":"UOM","width":160},
        {"fieldname":"today_apc_unit","label":"Today APC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"today_apc_prod","label":"Today APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"today_apc_cost","label":"Today APC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"apc_unit","label":"Todate APC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"apc_prod","label":"Todate APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"apc_cost","label":"Todate APC. Unit Cost","fieldtype":"Float","width":160},
        ]

        job_cards = frappe.db.get_all("Job Card",
                                      filters={
                                          "status":"Completed",
                                          "custom_stock_entry_reference":["!=",""],
                                          "posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],
                                          "operation":"Bag Manufacturing"
                                      },
                                      fields = ["production_item","workstation","total_completed_qty","posting_date"]
                                      )
        workstation={}

        for jc in job_cards:
            workstn = frappe.get_doc("Workstation",jc.workstation)
            units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jc.workstation},fields=["unit_consumption"],limit=1)
            itm = frappe.get_doc("Item",jc.production_item)
            if jc.workstation not in workstation:
                workstation[jc.workstation] = {
                    "date":jc.posting_date,
                    "workstation":jc.workstation,
                    # "ipc_unit":workstn.custom_ideal_unit_consumption,
                    # "ipc_prod":workstn.custom_ideal_production,
                    # "ipc_cost":workstn.custom_ideal_unit_cost,
                    "uom":f"Units/{itm.stock_uom}",
                    "today_apc_unit":0,
                    "today_apc_prod":0,
                    "today_apc_cost":0,
                    "apc_unit":0,
                    "apc_prod":0,
                    "apc_cost":0
                }
            workstation[jc.workstation]["today_apc_unit"] += units[0].get("unit_consumption") if units else 0
            workstation[jc.workstation]["today_apc_prod"] += jc.total_completed_qty

        todate_jc = frappe.db.get_all("Job Card",
                                      filters={
                                          "status":"Completed",
                                          "custom_stock_entry_reference":["!=",""],
                                          "posting_date":["<=",filters.get("to_date")],
                                          "operation":"Bag Manufacturing"
                                      },
                                      fields = ["production_item","workstation","total_completed_qty","posting_date"])
        for jcard in todate_jc:
            units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jcard.workstation},fields=["unit_consumption"],limit=1)

            if jcard.workstation in workstation:            
                workstation[jcard.workstation]["apc_unit"] += units[0].get("unit_consumption") if units else 0
                workstation[jcard.workstation]["apc_prod"] += jcard.total_completed_qty


        for wrkstn, vals in workstation.items():
            workstation[wrkstn]["today_apc_cost"] = vals["today_apc_unit"]/vals["today_apc_prod"] if vals["today_apc_prod"] else 0
            workstation[wrkstn]["apc_cost"] = vals["apc_unit"]/vals["apc_prod"] if vals["apc_prod"] else 0
            data.append(vals)        
            
            
            
            
            
            
            
    if filters.get("department")=="Packaging" and filters.get("specific_dept")=="Power":
        columns =[
        {"fieldname":"date","label":"Date","fieldtype":"Date","width":150},
        {"fieldname":"workstation","label":"Workstation","fieldtype":"Link","options":"Workstation","width":160},
        # {"fieldname":"ipc_unit","label":"IPC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"ipc_prod","label":"IPC. Production","fieldtype":"Float","width":160},
        # {"fieldname":"ipc_cost","label":"IPC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"uom","label":"UOM","fieldtype":"Link","options":"UOM","width":160},
        {"fieldname":"today_apc_unit","label":"Today APC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"today_apc_prod","label":"Today APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"today_apc_cost","label":"Today APC. Unit Cost","fieldtype":"Float","width":160},
        {"fieldname":"apc_unit","label":"Todate APC. Unit Cons.","fieldtype":"Float","width":160},
        # {"fieldname":"apc_prod","label":"Todate APC. Production","fieldtype":"Float","width":160},
        {"fieldname":"apc_cost","label":"Todate APC. Unit Cost","fieldtype":"Float","width":160},
        ]

        job_cards = frappe.db.get_all("Job Card",
                                      filters={
                                          "status":"Completed",
                                          "custom_stock_entry_reference":["!=",""],
                                          "posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],
                                          "operation":"Packaging"
                                      },
                                      fields = ["production_item","workstation","total_completed_qty","posting_date"]
                                      )
        workstation={}

        for jc in job_cards:
            workstn = frappe.get_doc("Workstation",jc.workstation)
            units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jc.workstation},fields=["unit_consumption"],limit=1)
            itm = frappe.get_doc("Item",jc.production_item)
            if jc.workstation not in workstation:
                workstation[jc.workstation] = {
                    "date":jc.posting_date,
                    "workstation":jc.workstation,
                    # "ipc_unit":workstn.custom_ideal_unit_consumption,
                    # "ipc_prod":workstn.custom_ideal_production,
                    # "ipc_cost":workstn.custom_ideal_unit_cost,
                    "uom":f"Units/{itm.stock_uom}",
                    "today_apc_unit":0,
                    "today_apc_prod":0,
                    "today_apc_cost":0,
                    "apc_unit":0,
                    "apc_prod":0,
                    "apc_cost":0
                }
            workstation[jc.workstation]["today_apc_unit"] += units[0].get("unit_consumption") if units else 0
            workstation[jc.workstation]["today_apc_prod"] += jc.total_completed_qty

        todate_jc = frappe.db.get_all("Job Card",
                                      filters={
                                          "status":"Completed",
                                          "custom_stock_entry_reference":["!=",""],
                                          "posting_date":["<=",filters.get("to_date")],
                                          "operation":"Packaging"
                                      },
                                      fields = ["production_item","workstation","total_completed_qty","posting_date"])
        for jcard in todate_jc:
            units = frappe.db.get_all("Machine Unit Consumption",filters={"posting_date":["between",[filters.get("from_date"),filters.get("to_date")]],"machine":jcard.workstation},fields=["unit_consumption"],limit=1)

            if jcard.workstation in workstation:            
                workstation[jcard.workstation]["apc_unit"] += units[0].get("unit_consumption") if units else 0
                workstation[jcard.workstation]["apc_prod"] += jcard.total_completed_qty


        for wrkstn, vals in workstation.items():
            workstation[wrkstn]["today_apc_cost"] = vals["today_apc_unit"]/vals["today_apc_prod"] if vals["today_apc_prod"] else 0
            workstation[wrkstn]["apc_cost"] = vals["apc_unit"]/vals["apc_prod"] if vals["apc_prod"] else 0
            data.append(vals)        
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
    # WASTAGE--------------------------------------------------------WASTAGE------------------------------------------------WASTAGE-----------
            
    if filters.get("department") == "Printing" and filters.get("specific_dept") == "Wastage":
    # ---- Columns ----
        columns = [
            {"label": "Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
            {"label": "Workstation", "fieldname": "department", "fieldtype": "Link", "options": "Workstation", "width": 150},
            {"label": "Shift A", "fieldname": "production", "fieldtype": "Float", "width": 150},
            {"label": "Today Waste (LBS)", "fieldname": "waste_lbs", "fieldtype": "Float", "width": 150},
            {"label": "Today Waste (KG)", "fieldname": "kg_waste", "fieldtype": "Float", "width": 150},
            {"label": "Waste ToDate (LBS)", "fieldname": "todate_waste_lbs", "fieldtype": "Float", "width": 150},
            {"label": "Waste ToDate (KG)", "fieldname": "todate_kg_waste", "fieldtype": "Float", "width": 150},
            # {"label": "Target", "fieldname": "target", "fieldtype": "Percent", "width": 150},
        ]

        data = []

        # ---- Fetch Job Cards ----
        job_cards = frappe.db.get_all(
            "Job Card",
            filters={
                "status": "Completed",
                "custom_stock_entry_reference": ["!=", ""],
                "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
                "operation": "Printing",
            },
            fields=["workstation", "total_completed_qty", "production_item", "custom_stock_entry_reference", "posting_date"],
            order_by="posting_date asc"
        )

        # Group by workstation AND date (composite key)
        dept = {}
        for entry in job_cards:
            item = frappe.get_doc("Item", entry.production_item)
            wkn = frappe.get_doc("Workstation", entry.workstation)
            kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"), None)
            se = frappe.get_doc("Stock Entry", entry.custom_stock_entry_reference)
            wastage = sum(itm.qty for itm in se.items if itm.is_scrap_item)

            # Create composite key: workstation + date
            composite_key = f"{entry.workstation}_{entry.posting_date}"

            if composite_key not in dept:
                dept[composite_key] = {
                    "posting_date": entry.posting_date,
                    "department": entry.workstation,
                    "uom": item.stock_uom,
                    "production": 0,
                    "waste_lbs": 0,
                    "kg_waste": 0,
                    "todate_waste_lbs": 0,
                    "todate_kg_waste": 0,
                    # "target": wkn.custom_target_wastage or 0,
                }

            # Accumulate values for this day/workstation
            dept[composite_key]["production"] += entry.total_completed_qty
            dept[composite_key]["waste_lbs"] += wastage
            if kg_conversion:
                dept[composite_key]["kg_waste"] += wastage * kg_conversion

        # --- Calculate ToDate waste and prepare data ---
        for key, vals in dept.items():
            # Optional: Calculate ToDate waste (all records up to this date for this workstation)
            jcs_todate = frappe.db.get_all(
                "Job Card",
                filters={
                    "workstation": vals["department"],
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "posting_date": ["between", [filters.get("from_date"), vals["posting_date"]]],
                },
                fields=["custom_stock_entry_reference", "total_completed_qty", "production_item"]
            )

            todate_waste_lbs = 0
            todate_waste_kg = 0

            for jc in jcs_todate:
                item = frappe.get_doc("Item", jc.production_item)
                kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"), None)
                se = frappe.get_doc("Stock Entry", jc.custom_stock_entry_reference)
                waste = sum(itm.qty for itm in se.items if itm.is_scrap_item)

                todate_waste_lbs += waste
                if kg_conversion:
                    todate_waste_kg += waste * kg_conversion

            vals["todate_waste_lbs"] = todate_waste_lbs
            vals["todate_kg_waste"] = todate_waste_kg
            
            
            
            data.append(vals)
            
        
        
    if filters.get("department") == "Slitting" and filters.get("specific_dept") == "Wastage":
    # ---- Columns ----
        columns = [
            {"label": "Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
            {"label": "Workstation", "fieldname": "department", "fieldtype": "Link", "options": "Workstation", "width": 150},
            {"label": "Shift A", "fieldname": "production", "fieldtype": "Float", "width": 150},
            {"label": "Today Waste (LBS)", "fieldname": "waste_lbs", "fieldtype": "Float", "width": 150},
            {"label": "Today Waste (KG)", "fieldname": "kg_waste", "fieldtype": "Float", "width": 150},
            {"label": "Waste ToDate (LBS)", "fieldname": "todate_waste_lbs", "fieldtype": "Float", "width": 150},
            {"label": "Waste ToDate (KG)", "fieldname": "todate_kg_waste", "fieldtype": "Float", "width": 150},
            # {"label": "Target", "fieldname": "target", "fieldtype": "Percent", "width": 150},
        ]

        data = []

        # ---- Fetch Job Cards ----
        job_cards = frappe.db.get_all(
            "Job Card",
            filters={
                "status": "Completed",
                "custom_stock_entry_reference": ["!=", ""],
                "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
                "operation": "Slitting",
            },
            fields=["workstation", "total_completed_qty", "production_item", "custom_stock_entry_reference", "posting_date"],
            order_by="posting_date asc"
        )

        # Group by workstation AND date (composite key)
        dept = {}
        for entry in job_cards:
            item = frappe.get_doc("Item", entry.production_item)
            wkn = frappe.get_doc("Workstation", entry.workstation)
            kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"), None)
            se = frappe.get_doc("Stock Entry", entry.custom_stock_entry_reference)
            wastage = sum(itm.qty for itm in se.items if itm.is_scrap_item)

            # Create composite key: workstation + date
            composite_key = f"{entry.workstation}_{entry.posting_date}"

            if composite_key not in dept:
                dept[composite_key] = {
                    "posting_date": entry.posting_date,
                    "department": entry.workstation,
                    "uom": item.stock_uom,
                    "production": 0,
                    "waste_lbs": 0,
                    "kg_waste": 0,
                    "todate_waste_lbs": 0,
                    "todate_kg_waste": 0,
                    # "target": wkn.custom_target_wastage or 0,
                }

            # Accumulate values for this day/workstation
            dept[composite_key]["production"] += entry.total_completed_qty
            dept[composite_key]["waste_lbs"] += wastage
            if kg_conversion:
                dept[composite_key]["kg_waste"] += wastage * kg_conversion

        # --- Calculate ToDate waste and prepare data ---
        for key, vals in dept.items():
            # Optional: Calculate ToDate waste (all records up to this date for this workstation)
            jcs_todate = frappe.db.get_all(
                "Job Card",
                filters={
                    "workstation": vals["department"],
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "posting_date": ["between", [filters.get("from_date"), vals["posting_date"]]],
                },
                fields=["custom_stock_entry_reference", "total_completed_qty", "production_item"]
            )

            todate_waste_lbs = 0
            todate_waste_kg = 0

            for jc in jcs_todate:
                item = frappe.get_doc("Item", jc.production_item)
                kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"), None)
                se = frappe.get_doc("Stock Entry", jc.custom_stock_entry_reference)
                waste = sum(itm.qty for itm in se.items if itm.is_scrap_item)

                todate_waste_lbs += waste
                if kg_conversion:
                    todate_waste_kg += waste * kg_conversion

            vals["todate_waste_lbs"] = todate_waste_lbs
            vals["todate_kg_waste"] = todate_waste_kg

            
            data.append(vals)
            
            
            
            
            
    if filters.get("department") == "AD*STARKON" and filters.get("specific_dept") == "Wastage":
    # ---- Columns ----
        columns = [
            {"label": "Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
            {"label": "Workstation", "fieldname": "department", "fieldtype": "Link", "options": "Workstation", "width": 150},
            {"label": "Shift A", "fieldname": "production", "fieldtype": "Float", "width": 150},
            {"label": "Today Waste (LBS)", "fieldname": "waste_lbs", "fieldtype": "Float", "width": 150},
            {"label": "Today Waste (KG)", "fieldname": "kg_waste", "fieldtype": "Float", "width": 150},
            {"label": "Waste ToDate (LBS)", "fieldname": "todate_waste_lbs", "fieldtype": "Float", "width": 150},
            {"label": "Waste ToDate (KG)", "fieldname": "todate_kg_waste", "fieldtype": "Float", "width": 150},
            # {"label": "Target", "fieldname": "target", "fieldtype": "Percent", "width": 150},
        ]

        data = []

        # ---- Fetch Job Cards ----
        job_cards = frappe.db.get_all(
            "Job Card",
            filters={
                "status": "Completed",
                "custom_stock_entry_reference": ["!=", ""],
                "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
                "operation": "Bag Manufacturing",
            },
            fields=["workstation", "total_completed_qty", "production_item", "custom_stock_entry_reference", "posting_date"],
            order_by="posting_date asc"
        )

        # Group by workstation AND date (composite key)
        dept = {}
        for entry in job_cards:
            item = frappe.get_doc("Item", entry.production_item)
            wkn = frappe.get_doc("Workstation", entry.workstation)
            kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"), None)
            se = frappe.get_doc("Stock Entry", entry.custom_stock_entry_reference)
            wastage = sum(itm.qty for itm in se.items if itm.is_scrap_item)

            # Create composite key: workstation + date
            composite_key = f"{entry.workstation}_{entry.posting_date}"

            if composite_key not in dept:
                dept[composite_key] = {
                    "posting_date": entry.posting_date,
                    "department": entry.workstation,
                    "uom": item.stock_uom,
                    "production": 0,
                    "waste_lbs": 0,
                    "kg_waste": 0,
                    "todate_waste_lbs": 0,
                    "todate_kg_waste": 0,
                    # "target": wkn.custom_target_wastage or 0,
                }

            # Accumulate values for this day/workstation
            dept[composite_key]["production"] += entry.total_completed_qty
            dept[composite_key]["waste_lbs"] += wastage
            if kg_conversion:
                dept[composite_key]["kg_waste"] += wastage * kg_conversion

        # --- Calculate ToDate waste and prepare data ---
        for key, vals in dept.items():
            # Optional: Calculate ToDate waste (all records up to this date for this workstation)
            jcs_todate = frappe.db.get_all(
                "Job Card",
                filters={
                    "workstation": vals["department"],
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "posting_date": ["between", [filters.get("from_date"), vals["posting_date"]]],
                },
                fields=["custom_stock_entry_reference", "total_completed_qty", "production_item"],
                order_by="posting_date asc"
            )

            todate_waste_lbs = 0
            todate_waste_kg = 0

            for jc in jcs_todate:
                item = frappe.get_doc("Item", jc.production_item)
                kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"), None)
                se = frappe.get_doc("Stock Entry", jc.custom_stock_entry_reference)
                waste = sum(itm.qty for itm in se.items if itm.is_scrap_item)

                todate_waste_lbs += waste
                if kg_conversion:
                    todate_waste_kg += waste * kg_conversion

            vals["todate_waste_lbs"] = todate_waste_lbs
            vals["todate_kg_waste"] = todate_waste_kg

            
            data.append(vals)
            
            
            
            
            
    if filters.get("department") == "Segregation" and filters.get("specific_dept") == "Wastage":
    # ---- Columns ----
        columns = [
            {"label": "Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
            {"label": "Workstation", "fieldname": "department", "fieldtype": "Link", "options": "Workstation", "width": 150},
            {"label": "Shift A", "fieldname": "production", "fieldtype": "Float", "width": 150},
            {"label": "Today Waste (LBS)", "fieldname": "waste_lbs", "fieldtype": "Float", "width": 150},
            {"label": "Today Waste (KG)", "fieldname": "kg_waste", "fieldtype": "Float", "width": 150},
            {"label": "Waste ToDate (LBS)", "fieldname": "todate_waste_lbs", "fieldtype": "Float", "width": 150},
            {"label": "Waste ToDate (KG)", "fieldname": "todate_kg_waste", "fieldtype": "Float", "width": 150},
            # {"label": "Target", "fieldname": "target", "fieldtype": "Percent", "width": 150},
        ]

        data = []

        # ---- Fetch Job Cards ----
        job_cards = frappe.db.get_all(
            "Job Card",
            filters={
                "status": "Completed",
                "custom_stock_entry_reference": ["!=", ""],
                "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
                "operation": "Segregation",
            },
            fields=["workstation", "total_completed_qty", "production_item", "custom_stock_entry_reference", "posting_date"],
            order_by="posting_date asc"
        )

        # Group by workstation AND date (composite key)
        dept = {}
        for entry in job_cards:
            item = frappe.get_doc("Item", entry.production_item)
            wkn = frappe.get_doc("Workstation", entry.workstation)
            kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"), None)
            se = frappe.get_doc("Stock Entry", entry.custom_stock_entry_reference)
            wastage = sum(itm.qty for itm in se.items if itm.is_scrap_item)

            # Create composite key: workstation + date
            composite_key = f"{entry.workstation}_{entry.posting_date}"

            if composite_key not in dept:
                dept[composite_key] = {
                    "posting_date": entry.posting_date,
                    "department": entry.workstation,
                    "uom": item.stock_uom,
                    "production": 0,
                    "waste_lbs": 0,
                    "kg_waste": 0,
                    "todate_waste_lbs": 0,
                    "todate_kg_waste": 0,
                    # "target": wkn.custom_target_wastage or 0,
                }

            # Accumulate values for this day/workstation
            dept[composite_key]["production"] += entry.total_completed_qty
            dept[composite_key]["waste_lbs"] += wastage
            if kg_conversion:
                dept[composite_key]["kg_waste"] += wastage * kg_conversion

        # --- Calculate ToDate waste and prepare data ---
        for key, vals in dept.items():
            # Optional: Calculate ToDate waste (all records up to this date for this workstation)
            jcs_todate = frappe.db.get_all(
                "Job Card",
                filters={
                    "workstation": vals["department"],
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "posting_date": ["between", [filters.get("from_date"), vals["posting_date"]]],
                },
                fields=["custom_stock_entry_reference", "total_completed_qty", "production_item"],
                order_by="posting_date asc"
            )

            todate_waste_lbs = 0
            todate_waste_kg = 0

            for jc in jcs_todate:
                item = frappe.get_doc("Item", jc.production_item)
                kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"), None)
                se = frappe.get_doc("Stock Entry", jc.custom_stock_entry_reference)
                waste = sum(itm.qty for itm in se.items if itm.is_scrap_item)

                todate_waste_lbs += waste
                if kg_conversion:
                    todate_waste_kg += waste * kg_conversion

            vals["todate_waste_lbs"] = todate_waste_lbs
            vals["todate_kg_waste"] = todate_waste_kg

            
            data.append(vals)
            
    
    if filters.get("department") == "Packaging" and filters.get("specific_dept") == "Wastage":
    # ---- Columns ----
        columns = [
            {"label": "Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
            {"label": "Workstation", "fieldname": "department", "fieldtype": "Link", "options": "Workstation", "width": 150},
            {"label": "Shift A", "fieldname": "production", "fieldtype": "Float", "width": 150},
            {"label": "Today Waste (LBS)", "fieldname": "waste_lbs", "fieldtype": "Float", "width": 150},
            {"label": "Today Waste (KG)", "fieldname": "kg_waste", "fieldtype": "Float", "width": 150},
            {"label": "Waste ToDate (LBS)", "fieldname": "todate_waste_lbs", "fieldtype": "Float", "width": 150},
            {"label": "Waste ToDate (KG)", "fieldname": "todate_kg_waste", "fieldtype": "Float", "width": 150},
            # {"label": "Target", "fieldname": "target", "fieldtype": "Percent", "width": 150},
        ]

        data = []

        # ---- Fetch Job Cards ----
        job_cards = frappe.db.get_all(
            "Job Card",
            filters={
                "status": "Completed",
                "custom_stock_entry_reference": ["!=", ""],
                "posting_date": ["between", [filters.get("from_date"), filters.get("to_date")]],
                "operation": "Packaging",
            },
            fields=["workstation", "total_completed_qty", "production_item", "custom_stock_entry_reference", "posting_date"],
            order_by="posting_date asc"
        )

        # Group by workstation AND date (composite key)
        dept = {}
        for entry in job_cards:
            item = frappe.get_doc("Item", entry.production_item)
            wkn = frappe.get_doc("Workstation", entry.workstation)
            kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"), None)
            se = frappe.get_doc("Stock Entry", entry.custom_stock_entry_reference)
            wastage = sum(itm.qty for itm in se.items if itm.is_scrap_item)

            # Create composite key: workstation + date
            composite_key = f"{entry.workstation}_{entry.posting_date}"

            if composite_key not in dept:
                dept[composite_key] = {
                    "posting_date": entry.posting_date,
                    "department": entry.workstation,
                    "uom": item.stock_uom,
                    "production": 0,
                    "waste_lbs": 0,
                    "kg_waste": 0,
                    "todate_waste_lbs": 0,
                    "todate_kg_waste": 0,
                    # "target": wkn.custom_target_wastage or 0,
                }

            # Accumulate values for this day/workstation
            dept[composite_key]["production"] += entry.total_completed_qty
            dept[composite_key]["waste_lbs"] += wastage
            if kg_conversion:
                dept[composite_key]["kg_waste"] += wastage * kg_conversion

        # --- Calculate ToDate waste and prepare data ---
        for key, vals in dept.items():
            # Optional: Calculate ToDate waste (all records up to this date for this workstation)
            jcs_todate = frappe.db.get_all(
                "Job Card",
                filters={
                    "workstation": vals["department"],
                    "status": "Completed",
                    "custom_stock_entry_reference": ["!=", ""],
                    "posting_date": ["between", [filters.get("from_date"), vals["posting_date"]]],
                },
                fields=["custom_stock_entry_reference", "total_completed_qty", "production_item"]
            )

            todate_waste_lbs = 0
            todate_waste_kg = 0

            for jc in jcs_todate:
                item = frappe.get_doc("Item", jc.production_item)
                kg_conversion = next((itm.conversion_factor for itm in item.uoms if itm.uom == "Kg"), None)
                se = frappe.get_doc("Stock Entry", jc.custom_stock_entry_reference)
                waste = sum(itm.qty for itm in se.items if itm.is_scrap_item)

                todate_waste_lbs += waste
                if kg_conversion:
                    todate_waste_kg += waste * kg_conversion

            vals["todate_waste_lbs"] = todate_waste_lbs
            vals["todate_kg_waste"] = todate_waste_kg

            
            data.append(vals)
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
        
            
            
            
    # BOM VS ACTUAL---------------------------------------BOM VS ACTUAL-----------------------------------------BOM VS ACTUAL--
    
    
    if filters.get("department")=="Printing" and filters.get("specific_dept")=="BOM vs Actual":
        columns = [
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
        {"label": "Work Order", "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 200},
        {"label": "Material", "fieldname": "material", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": "Material Description", "fieldname": "material_desc", "fieldtype": "Data", "width": 180},
        {"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        # {"label": "Order Qty", "fieldname": "order_qty", "fieldtype": "Float", "width": 100},
        # {"label": "Production Qty", "fieldname": "production_qty", "fieldtype": "Float", "width": 120},
        # {"label": "Pending Order Qty", "fieldname": "pending_order_qty", "fieldtype": "Float", "width": 120},
        {"label": "Component", "fieldname": "component", "fieldtype": "Link", "options": "Item", "width": 120},
        # {"label": "Component Description", "fieldname": "component_desc", "fieldtype": "Data", "width": 180},
        {"label": "Com UOM", "fieldname": "com_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": "Required Qty", "fieldname": "required_qty", "fieldtype": "Float", "width": 100},
        {"label": "Actual Qty", "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
        {"label": "Difference Qty", "fieldname": "diff_qty", "fieldtype": "Float", "width": 120},
        # {"label": "Req. %", "fieldname": "req_percent", "fieldtype": "Percent", "width": 80},
        # {"label": "Act. %", "fieldname": "act_percent", "fieldtype": "Percent", "width": 80},
        ]

        data = []
        
        wo_names = frappe.get_all(
            "Work Order Operation",
            filters={"operation":"Printing"},
            pluck="parent"
        )

        work_orders = frappe.get_all(
            "Work Order",
            filters={"status": "Completed","name":["in",wo_names],"creation":["between",[filters.get("from_date"),filters.get("to_date")]]},
            fields=["name", "qty", "produced_qty", "production_item", "creation"]
        )

        for wo in work_orders:
            required_items = frappe.get_all(
                "Work Order Item",
                filters={"parent": wo.name},
                fields=["item_code", "description", "stock_uom", "required_qty"]
            )
            req_total = sum(itm.required_qty for itm in required_items)

            actual_items = frappe.get_all(
                "Work Order Item",
                filters={"parent": wo.name},
                fields=["item_code", "consumed_qty"]
            )

            actual_map = {a.item_code: a.consumed_qty for a in actual_items}

            actual_sum = sum(itm.consumed_qty for itm in actual_items)

            for req in required_items:
                actual_qty = actual_map.get(req.item_code, 0)
                diff_qty = actual_qty - req.required_qty

                row = {
                    "work_order": wo.name,
                    "material": wo.production_item,
                    "material_desc": frappe.db.get_value("Item", wo.production_item, "description"),
                    "uom": frappe.db.get_value("Item", wo.production_item, "stock_uom"),
                    "component": req.item_code,
                    "component_desc": req.description,
                    "com_uom": frappe.db.get_value("Item", req.item_code, "stock_uom"),
                    "order_qty": wo.qty,
                    "pending_order_qty": wo.qty - wo.produced_qty,
                    "production_qty": wo.produced_qty,
                    "required_qty": req.required_qty,
                    "actual_qty": actual_qty or "",
                    "diff_qty": diff_qty,
                    "posting_date": wo.creation.date(),
                    # "req_percent": (req.required_qty/req_total)*100,
                    # "act_percent": (actual_qty/actual_sum)*100,
                }
                data.append(row)
            
            
            
    if filters.get("department")=="Slitting" and filters.get("specific_dept")=="BOM vs Actual":
        columns = [
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
        {"label": "Work Order", "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 200},
        {"label": "Material", "fieldname": "material", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": "Material Description", "fieldname": "material_desc", "fieldtype": "Data", "width": 180},
        {"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        # {"label": "Order Qty", "fieldname": "order_qty", "fieldtype": "Float", "width": 100},
        # {"label": "Production Qty", "fieldname": "production_qty", "fieldtype": "Float", "width": 120},
        # {"label": "Pending Order Qty", "fieldname": "pending_order_qty", "fieldtype": "Float", "width": 120},
        {"label": "Component", "fieldname": "component", "fieldtype": "Link", "options": "Item", "width": 120},
        # {"label": "Component Description", "fieldname": "component_desc", "fieldtype": "Data", "width": 180},
        {"label": "Com UOM", "fieldname": "com_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": "Required Qty", "fieldname": "required_qty", "fieldtype": "Float", "width": 100},
        {"label": "Actual Qty", "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
        {"label": "Difference Qty", "fieldname": "diff_qty", "fieldtype": "Float", "width": 120},
        # {"label": "Req. %", "fieldname": "req_percent", "fieldtype": "Percent", "width": 80},
        # {"label": "Act. %", "fieldname": "act_percent", "fieldtype": "Percent", "width": 80},
        ]

        data = []
        
        wo_names = frappe.get_all(
            "Work Order Operation",
            filters={"operation":"Slitting"},
            pluck="parent"
        )

        work_orders = frappe.get_all(
            "Work Order",
            filters={"status": "Completed","name":["in",wo_names],"creation":["between",[filters.get("from_date"),filters.get("to_date")]]},
            fields=["name", "qty", "produced_qty", "production_item", "creation"]
        )

        for wo in work_orders:
            required_items = frappe.get_all(
                "Work Order Item",
                filters={"parent": wo.name},
                fields=["item_code", "description", "stock_uom", "required_qty"]
            )
            req_total = sum(itm.required_qty for itm in required_items)

            actual_items = frappe.get_all(
                "Work Order Item",
                filters={"parent": wo.name},
                fields=["item_code", "consumed_qty"]
            )

            actual_map = {a.item_code: a.consumed_qty for a in actual_items}

            actual_sum = sum(itm.consumed_qty for itm in actual_items)

            for req in required_items:
                actual_qty = actual_map.get(req.item_code, 0)
                diff_qty = actual_qty - req.required_qty

                row = {
                    "work_order": wo.name,
                    "material": wo.production_item,
                    "material_desc": frappe.db.get_value("Item", wo.production_item, "description"),
                    "uom": frappe.db.get_value("Item", wo.production_item, "stock_uom"),
                    "component": req.item_code,
                    "component_desc": req.description,
                    "com_uom": frappe.db.get_value("Item", req.item_code, "stock_uom"),
                    "order_qty": wo.qty,
                    "pending_order_qty": wo.qty - wo.produced_qty,
                    "production_qty": wo.produced_qty,
                    "required_qty": req.required_qty,
                    "actual_qty": actual_qty or "",
                    "diff_qty": diff_qty,
                    "posting_date": wo.creation.date(),
                    # "req_percent": (req.required_qty/req_total)*100,
                    # "act_percent": (actual_qty/actual_sum)*100,
                }
                data.append(row)
            
            
            
            
    if filters.get("department")=="AD*STARKON" and filters.get("specific_dept")=="BOM vs Actual":
        columns = [
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
        {"label": "Work Order", "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 200},
        {"label": "Material", "fieldname": "material", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": "Material Description", "fieldname": "material_desc", "fieldtype": "Data", "width": 180},
        {"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        # {"label": "Order Qty", "fieldname": "order_qty", "fieldtype": "Float", "width": 100},
        # {"label": "Production Qty", "fieldname": "production_qty", "fieldtype": "Float", "width": 120},
        # {"label": "Pending Order Qty", "fieldname": "pending_order_qty", "fieldtype": "Float", "width": 120},
        {"label": "Component", "fieldname": "component", "fieldtype": "Link", "options": "Item", "width": 120},
        # {"label": "Component Description", "fieldname": "component_desc", "fieldtype": "Data", "width": 180},
        {"label": "Com UOM", "fieldname": "com_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": "Required Qty", "fieldname": "required_qty", "fieldtype": "Float", "width": 100},
        {"label": "Actual Qty", "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
        {"label": "Difference Qty", "fieldname": "diff_qty", "fieldtype": "Float", "width": 120},
        # {"label": "Req. %", "fieldname": "req_percent", "fieldtype": "Percent", "width": 80},
        # {"label": "Act. %", "fieldname": "act_percent", "fieldtype": "Percent", "width": 80},
        ]

        data = []
        
        wo_names = frappe.get_all(
            "Work Order Operation",
            filters={"operation":"Bag Manufacturing"},
            pluck="parent"
        )
        if not wo_names:
            return columns, []

        work_orders = frappe.get_all(
            "Work Order",
            filters={"status": "Completed","name":["in",wo_names],"creation":["between",[filters.get("from_date"),filters.get("to_date")]]},
            fields=["name", "qty", "produced_qty", "production_item", "creation"]
        )

        for wo in work_orders:
            required_items = frappe.get_all(
                "Work Order Item",
                filters={"parent": wo.name},
                fields=["item_code", "description", "stock_uom", "required_qty"]
            )
            req_total = sum(itm.required_qty for itm in required_items)

            actual_items = frappe.get_all(
                "Work Order Item",
                filters={"parent": wo.name},
                fields=["item_code", "consumed_qty"]
            )

            actual_map = {a.item_code: a.consumed_qty for a in actual_items}

            actual_sum = sum(itm.consumed_qty for itm in actual_items)

            for req in required_items:
                actual_qty = actual_map.get(req.item_code, 0)
                diff_qty = actual_qty - req.required_qty

                row = {
                    "work_order": wo.name,
                    "material": wo.production_item,
                    "material_desc": frappe.db.get_value("Item", wo.production_item, "description"),
                    "uom": frappe.db.get_value("Item", wo.production_item, "stock_uom"),
                    "component": req.item_code,
                    "component_desc": req.description,
                    "com_uom": frappe.db.get_value("Item", req.item_code, "stock_uom"),
                    "order_qty": wo.qty,
                    "pending_order_qty": wo.qty - wo.produced_qty,
                    "production_qty": wo.produced_qty,
                    "required_qty": req.required_qty,
                    "actual_qty": actual_qty or "",
                    "diff_qty": diff_qty,
                    "posting_date": wo.creation.date(),
                    # "req_percent": (req.required_qty/req_total)*100,
                    # "act_percent": (actual_qty/actual_sum)*100,
                }
                data.append(row)
                
                
                
                
                
    if filters.get("department")=="Segregation" and filters.get("specific_dept")=="BOM vs Actual":
        columns = [
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
        {"label": "Work Order", "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 200},
        {"label": "Material", "fieldname": "material", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": "Material Description", "fieldname": "material_desc", "fieldtype": "Data", "width": 180},
        {"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        # {"label": "Order Qty", "fieldname": "order_qty", "fieldtype": "Float", "width": 100},
        # {"label": "Production Qty", "fieldname": "production_qty", "fieldtype": "Float", "width": 120},
        # {"label": "Pending Order Qty", "fieldname": "pending_order_qty", "fieldtype": "Float", "width": 120},
        {"label": "Component", "fieldname": "component", "fieldtype": "Link", "options": "Item", "width": 120},
        # {"label": "Component Description", "fieldname": "component_desc", "fieldtype": "Data", "width": 180},
        {"label": "Com UOM", "fieldname": "com_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": "Required Qty", "fieldname": "required_qty", "fieldtype": "Float", "width": 100},
        {"label": "Actual Qty", "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
        {"label": "Difference Qty", "fieldname": "diff_qty", "fieldtype": "Float", "width": 120},
        # {"label": "Req. %", "fieldname": "req_percent", "fieldtype": "Percent", "width": 80},
        # {"label": "Act. %", "fieldname": "act_percent", "fieldtype": "Percent", "width": 80},
        ]

        data = []
        
        wo_names = frappe.get_all(
            "Work Order Operation",
            filters={"operation":"Segregation"},
            pluck="parent"
        )

        work_orders = frappe.get_all(
            "Work Order",
            filters={"status": "Completed","name":["in",wo_names],"creation":["between",[filters.get("from_date"),filters.get("to_date")]]},
            fields=["name", "qty", "produced_qty", "production_item", "creation"]
        )

        for wo in work_orders:
            required_items = frappe.get_all(
                "Work Order Item",
                filters={"parent": wo.name},
                fields=["item_code", "description", "stock_uom", "required_qty"]
            )
            req_total = sum(itm.required_qty for itm in required_items)

            actual_items = frappe.get_all(
                "Work Order Item",
                filters={"parent": wo.name},
                fields=["item_code", "consumed_qty"]
            )

            actual_map = {a.item_code: a.consumed_qty for a in actual_items}

            actual_sum = sum(itm.consumed_qty for itm in actual_items)

            for req in required_items:
                actual_qty = actual_map.get(req.item_code, 0)
                diff_qty = actual_qty - req.required_qty

                row = {
                    "work_order": wo.name,
                    "material": wo.production_item,
                    "material_desc": frappe.db.get_value("Item", wo.production_item, "description"),
                    "uom": frappe.db.get_value("Item", wo.production_item, "stock_uom"),
                    "component": req.item_code,
                    "component_desc": req.description,
                    "com_uom": frappe.db.get_value("Item", req.item_code, "stock_uom"),
                    "order_qty": wo.qty,
                    "pending_order_qty": wo.qty - wo.produced_qty,
                    "production_qty": wo.produced_qty,
                    "required_qty": req.required_qty,
                    "actual_qty": actual_qty or "",
                    "diff_qty": diff_qty,
                    "posting_date": wo.creation.date(),
                    # "req_percent": (req.required_qty/req_total)*100,
                    # "act_percent": (actual_qty/actual_sum)*100,
                }
                data.append(row)
                
                
                
                
    if filters.get("department")=="Packaging" and filters.get("specific_dept")=="BOM vs Actual":
        columns = [
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
        {"label": "Work Order", "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 200},
        {"label": "Material", "fieldname": "material", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": "Material Description", "fieldname": "material_desc", "fieldtype": "Data", "width": 180},
        {"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        # {"label": "Order Qty", "fieldname": "order_qty", "fieldtype": "Float", "width": 100},
        # {"label": "Production Qty", "fieldname": "production_qty", "fieldtype": "Float", "width": 120},
        # {"label": "Pending Order Qty", "fieldname": "pending_order_qty", "fieldtype": "Float", "width": 120},
        {"label": "Component", "fieldname": "component", "fieldtype": "Link", "options": "Item", "width": 120},
        # {"label": "Component Description", "fieldname": "component_desc", "fieldtype": "Data", "width": 180},
        {"label": "Com UOM", "fieldname": "com_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": "Required Qty", "fieldname": "required_qty", "fieldtype": "Float", "width": 100},
        {"label": "Actual Qty", "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
        {"label": "Difference Qty", "fieldname": "diff_qty", "fieldtype": "Float", "width": 120},
        # {"label": "Req. %", "fieldname": "req_percent", "fieldtype": "Percent", "width": 80},
        # {"label": "Act. %", "fieldname": "act_percent", "fieldtype": "Percent", "width": 80},
        ]

        data = []
        
        wo_names = frappe.get_all(
            "Work Order Operation",
            filters={"operation":"Packaging"},
            pluck="parent"
        )

        work_orders = frappe.get_all(
            "Work Order",
            filters={"status": "Completed","name":["in",wo_names],"creation":["between",[filters.get("from_date"),filters.get("to_date")]]},
            fields=["name", "qty", "produced_qty", "production_item", "creation"]
        )

        for wo in work_orders:
            required_items = frappe.get_all(
                "Work Order Item",
                filters={"parent": wo.name},
                fields=["item_code", "description", "stock_uom", "required_qty"]
            )
            req_total = sum(itm.required_qty for itm in required_items)

            actual_items = frappe.get_all(
                "Work Order Item",
                filters={"parent": wo.name},
                fields=["item_code", "consumed_qty"]
            )

            actual_map = {a.item_code: a.consumed_qty for a in actual_items}

            actual_sum = sum(itm.consumed_qty for itm in actual_items)

            for req in required_items:
                actual_qty = actual_map.get(req.item_code, 0)
                diff_qty = actual_qty - req.required_qty

                row = {
                    "work_order": wo.name,
                    "material": wo.production_item,
                    "material_desc": frappe.db.get_value("Item", wo.production_item, "description"),
                    "uom": frappe.db.get_value("Item", wo.production_item, "stock_uom"),
                    "component": req.item_code,
                    "component_desc": req.description,
                    "com_uom": frappe.db.get_value("Item", req.item_code, "stock_uom"),
                    "order_qty": wo.qty,
                    "pending_order_qty": wo.qty - wo.produced_qty,
                    "production_qty": wo.produced_qty,
                    "required_qty": req.required_qty,
                    "actual_qty": actual_qty or "",
                    "diff_qty": diff_qty,
                    "posting_date": wo.creation.date(),
                    # "req_percent": (req.required_qty/req_total)*100,
                    # "act_percent": (actual_qty/actual_sum)*100,
                }
                data.append(row)            
                
                
                
    return columns, data



    