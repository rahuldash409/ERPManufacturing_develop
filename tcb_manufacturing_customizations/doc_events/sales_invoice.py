import frappe
from frappe.utils import flt


def copy_bales_from_delivery_note(doc, method=None):
    """
    Copy bales from linked Delivery Notes to Sales Invoice's custom_bales_used table.
    Called on validate to ensure bales are copied when SI is created from DN.
    """
    if not doc.items:
        return

    # Get unique delivery notes from items
    delivery_notes = set()
    for item in doc.items:
        if item.delivery_note:
            delivery_notes.add(item.delivery_note)

    if not delivery_notes:
        return

    # Get existing bales in SI to avoid duplicates
    existing_bales = {row.bale for row in doc.custom_bales_used} if doc.custom_bales_used else set()

    # Fetch bales from each Delivery Note
    for dn_name in delivery_notes:
        # Get Delivery Note Bales document
        dn_bales_doc = frappe.db.get_value(
            "Delivery Note Bales", {"delivery_note": dn_name}, "name"
        )

        if not dn_bales_doc:
            continue

        # Get bales details
        bales_details = frappe.get_all(
            "Delivery Note Bales Detail",
            filters={"parent": dn_bales_doc},
            fields=["bale", "item", "qty"],
        )

        # Add bales to Sales Invoice
        for bale_data in bales_details:
            if bale_data.bale not in existing_bales:
                doc.append(
                    "custom_bales_used",
                    {
                        "bale": bale_data.bale,
                        "item": bale_data.item,
                        "qty": flt(bale_data.qty),
                    },
                )
                existing_bales.add(bale_data.bale)


# @frappe.whitelist()
# def set_segregated_bags_qty(docname,sum_qty):
#     frappe.db.set_value("Sales Invoice",docname,"custom_total_segregated_bags_qty",sum_qty)
#     return True