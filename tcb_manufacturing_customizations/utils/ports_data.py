import frappe

@frappe.whitelist()
def create_ports():
    # Sample Domestic Ports
    domestic_ports = [
        "Mumbai Port",
        "Chennai Port",
        "Kolkata Port",
        "Cochin Port",
        "Kandla Port"
    ]

    # Sample International Ports
    international_ports = [
        "Port of Singapore",
        "Port of Shanghai",
        "Port of Rotterdam",
        "Port of Dubai (Jebel Ali)",
        "Port of Hamburg"
    ]

    # Create Domestic Ports
    for port in domestic_ports:
        if not frappe.db.exists("Port", {"port_name": port}):
            doc = frappe.get_doc({
                "doctype": "Port",
                "port_name": port,
                "delivery_type": "Domestic"
            })
            doc.insert(ignore_permissions=True)

    # Create International Ports
    for port in international_ports:
        if not frappe.db.exists("Port", {"port_name": port}):
            doc = frappe.get_doc({
                "doctype": "Port",
                "port_name": port,
                "delivery_type": "International"
            })
            doc.insert(ignore_permissions=True)

    frappe.db.commit()
    frappe.msgprint("✅ Domestic & International Ports inserted successfully!")
