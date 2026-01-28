import frappe

def validate(doc, method=None):
    if isinstance(doc.custom_excess_material__required,(int,float)):
        if doc.custom_excess_material__required >= 0 and doc.items:
            for item in doc.items:
                actual = item.custom_excess_qty
                item.qty = actual + (actual * (doc.custom_excess_material__required / 100))
                for itm in doc.exploded_items:
                    if itm.item_code == item.item_code:
                        itm.stock_qty = item.qty
                
                
                
def test():
    attendances = frappe.db.get_all("Attendance",
                                   filters= {"attendance_date":"2025-11-11"},
                                   fields = ["status","employee"])
    stores = 0
    cleaning = 0
    admin = 0
    for attendance in attendances:
        if attendance.status=="Present":
            dept = frappe.db.get_value("Employee",attendance.employee,"department",as_dict=True)
            
            if dept.department == "Stores - APUI":
                stores +=1
            elif dept.department=="Administration - APUI":
                admin +=1
            elif dept.department == "Cleaning - APUI":
                cleaning+=1
    print(stores)
    print(cleaning)
    print(admin)
