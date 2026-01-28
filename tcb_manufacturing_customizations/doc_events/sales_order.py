import frappe


def rem_taxes(doc,method=None):
    if doc.taxes_and_charges:
        doc.taxes_and_charges = ""
    
    if doc.taxes:
        doc.set("taxes",[])