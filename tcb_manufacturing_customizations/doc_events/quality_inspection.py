import frappe

def validate(doc,method=None):
    for row in doc.readings:
        readings = [
            row.reading_1,row.reading_2,row.reading_3,row.reading_4,row.reading_5,row.reading_6,row.reading_7,row.reading_8,row.reading_9,row.reading_10
        ]
        
        valid_readings = [r for r in readings if r is not None and r is not ""]
        converted_readings = []
        for reading in valid_readings:
            converted_readings.append(float(reading))
        
        if valid_readings:
            avg_readings = sum(converted_readings)/len(converted_readings)
        else:
            avg_readings = 0
        
        row.custom_average_reading = avg_readings
        # Dont use the db.set_value on validate unless editing another doc
        # frappe.db.set_value(row.doctype,row.name,"custom_average_reading",avg_readings)
        