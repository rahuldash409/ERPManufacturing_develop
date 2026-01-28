import frappe

# List of default item properties with their UOMs
BAG_ITEM_PROPERTIES = [
    {"property": "Bag Material", "uom": ""},
    {"property": "Bag Type", "uom": ""},
    {"property": "Stitching Type", "uom": ""},
    {"property": "Valve or Open Mouth", "uom": ""},
    {"property": "Bottom Patch Type", "uom": ""},
    {"property": "Valve Type", "uom": ""},
    {"property": "Valve Material", "uom": ""},
    {"property": "Valve Direction", "uom": ""},
    {"property": "Number Of Ply", "uom": ""},
    {"property": "First Ply", "uom": ""},
    {"property": "Second Ply", "uom": ""},
    {"property": "Length", "uom": "mm"},
    {"property": "Width", "uom": "mm"},
    {"property": "Stitch Single fold mm", "uom": "mm"},
    {"property": "Top Width", "uom": "mm"},
    {"property": "Bottom Width", "uom": "mm"},
    {"property": "Valve Depth", "uom": "mm"},
    {"property": "Extended Valve", "uom": "mm"},
    {"property": "Pocket", "uom": "mm"},
    {"property": "Gusset", "uom": "mm"},
    {"property": "Perforation", "uom": ""},
    {"property": "BOPP Micron", "uom": ""},
    {"property": "First/Fabric GSM", "uom": "Gram/Square Meter"},
    {"property": "Lamination GSM", "uom": "Gram/Square Meter"},
    {"property": "Second Ply GSM", "uom": "Gram/Square Meter"},
    {"property": "Bag Overlap", "uom": "mm"},
    {"property": "Packing", "uom": "Nos"},
    {"property": "Colour of Base Fabric", "uom": ""},
    {"property": "UV s", "uom": ""},
    {"property": "UV %", "uom": "Percent"},
    {"property": "GripTech", "uom": ""},
    {"property": "GSM for Griptech", "uom": "Gram/Square Meter"},
    {"property": "Total weight", "uom": "Gram"},
    {"property": "Remarks", "uom": ""},
]
FABRIC_ITEM_PROPERTIES = [
    {"property": "First/Fabric GSM", "uom": "Gram/Square Meter"},
    {"property": "Lamination GSM", "uom": "Gram/Square Meter"},
    {"property": "Fabric Width", "uom": "mm"},
    {"property": "Fabric Meter Weight", "uom": "Gram"},

]

# Extract unique UOMs from BAG_ITEM_PROPERTIES
REQUIRED_UOMS = sorted({prop["uom"] for prop in BAG_ITEM_PROPERTIES if prop["uom"]})

def create_uom_masters():
    """Create required UOM master records if they don't exist"""
    #print("Creating UOM Masters...")
    
    for uom_name in REQUIRED_UOMS:
        if not frappe.db.exists("UOM", uom_name):
            try:
                uom_doc = frappe.new_doc("UOM")
                uom_doc.uom_name = uom_name
                uom_doc.insert(ignore_permissions=True)
                #print(f"Created UOM: {uom_name}")
            except Exception as e:
                #print(f"Error creating UOM {uom_name}: {str(e)}")
                frappe.log_error("Error creating UOM", f"Error creating UOM {uom_name}: {str(e)}")
        # else:
        #     print(f"UOM already exists: {uom_name}")

def create_item_property_masters():
    """Create Item Property master records if they don't exist"""
    #print("Creating Item Property Masters...")
    combined_properties = BAG_ITEM_PROPERTIES + FABRIC_ITEM_PROPERTIES
    for prop_data in combined_properties:
        property_name = prop_data["property"]
        
        if not frappe.db.exists("Item Property", property_name):
            try:
                item_property = frappe.new_doc("Item Property")
                item_property.property_name = property_name
                item_property.insert(ignore_permissions=True)
                #print(f"Created Item Property: {property_name}")
            except Exception as e:
                #print(f"Error creating Item Property {property_name}: {str(e)}")
                frappe.log_error("Error creating Item Property", f"Error creating Item Property {property_name}: {str(e)}")
        # else:
        #     print(f"Item Property already exists: {property_name}")

def add_default_properties_to_item(item_doc):
    """Add default properties to an item if they don't exist"""
    # #print(f"Adding default properties to item: {item_doc.name}")
    
    existing_properties = set()
    if item_doc.custom_item_property_detail:
        existing_properties = {prop.item_property for prop in item_doc.custom_item_property_detail}
    
    relevant_properties = []
    if "fabric" in item_doc.item_group:
        relevant_properties += FABRIC_ITEM_PROPERTIES
        # #print('=============== item doc === fabric if condition ==',relevant_properties)
    if "bag" in item_doc.item_group:
        relevant_properties += BAG_ITEM_PROPERTIES
        # #print('=============== item doc ===  else condition ==',relevant_properties)
    
    # #print('============== relevant properties ==', relevant_properties)

    for prop_data in relevant_properties:
        property_name = prop_data["property"]
        uom = prop_data["uom"]
        
        if property_name not in existing_properties:
            item_doc.append("custom_item_property_detail", {
                "item_property": property_name,
                "uom": uom,
                "value": ""
            })
            #print(f"Added property: {property_name} with UOM: {uom}")

def update_all_existing_items():
    """Update all existing items with default properties"""
    #print("Updating all existing items...")
    
    create_item_property_masters()
    
    items = frappe.get_all("Item", fields=["name"])
    
    for item in items:
        try:
            item_doc = frappe.get_doc("Item", item.name)
            existing_properties = set()
            if item_doc.custom_item_property_detail:
                existing_properties = {prop.item_property for prop in item_doc.custom_item_property_detail}
            
            # relevant_properties = []
                # #print('=============== item doc === fabric if condition ==',relevant_properties)
            # if "fabric" in item_doc.item_group:
            #     required_properties = {prop["property"] for prop in FABRIC_ITEM_PROPERTIES}
            # elif "bags" in item_doc.item_group:
            #     required_properties = {prop["property"] for prop in BAG_ITEM_PROPERTIES}
            
            relevant_properties = []
            if "fabric" in item_doc.item_group:
                relevant_properties += FABRIC_ITEM_PROPERTIES
                # #print('=============== item doc === fabric if condition ==',relevant_properties)
            if "bag" in item_doc.item_group:
                relevant_properties += BAG_ITEM_PROPERTIES
                
                
            relevant_property_names = {prop["property"] for prop in relevant_properties}
            
            rows_to_remove = []
            for idx, prop_row in enumerate(item_doc.custom_item_property_detail):
                if prop_row.item_property not in relevant_property_names:
                    rows_to_remove.append(idx)
                    #print(f"Marking for removal: {prop_row.item_property} from item {item_doc.name}")
            
            # Remove rows in reverse order to avoid index shifting issues
            for idx in reversed(rows_to_remove):
                item_doc.custom_item_property_detail.pop(idx)
                #print(f"Removed property at index {idx}")
            
            # Add missing properties
            for prop_data in relevant_properties:
                property_name = prop_data["property"]
                uom = prop_data["uom"]
                if property_name not in existing_properties:
                    item_doc.append("custom_item_property_detail", {
                        "item_property": property_name,
                        "uom": uom,
                        "value": ""
                    })
                    #print(f"Added property: {property_name} with UOM: {uom} to item {item_doc.name}")
            
            # Save if there were any changes (additions or removals)
            if rows_to_remove or (relevant_property_names - existing_properties):
                item_doc.save(ignore_permissions=True)
                #print(f"Updated item: {item_doc.name}")
            # else:
            #     print(f"Item {item_doc.name} already has correct properties")
                
        except Exception as e:
            # print(f"Error updating item {item.name}: {str(e)}")
            frappe.log_error(f"Error updating item {item.name}: {str(e)}")

def auto_add_properties_to_new_item(doc, method=None):
    """Hook function to automatically add properties to new items"""
    # #print(f"Auto-adding properties to new item: {doc.name}")
    
    create_item_property_masters()
    add_default_properties_to_item(doc)
    
    # #print(f"Properties added to item: {doc.name}")
    
@frappe.whitelist()
def setup_item_properties():
    """One-time setup function to create UOMs, Item Properties and update existing items"""
    #print("Starting Item Properties setup...")
    
    try:
        create_uom_masters()
        frappe.db.commit()
        
        create_item_property_masters()
        frappe.db.commit()
        
        update_all_existing_items()
        frappe.db.commit()
        
        #print("Item Properties setup completed successfully!")
        return "Setup completed successfully!"
        
    except Exception as e:
        frappe.db.rollback()
        error_msg = f"Error in setup_item_properties: {str(e)}"
        #print(error_msg)
        frappe.log_error("Error in setup_item_properties", error_msg)
        return f"Setup failed: {str(e)}"
