import frappe
from frappe.utils import flt
import math

@frappe.whitelist()
def add_baling_to_mr_items(production_plan_name):
    """
    Calculate baling materials and return data to frontend
    Frontend will add them to avoid document conflicts
    """
    pp = frappe.get_doc("Production Plan", production_plan_name)
    
    # Get baling requirements
    baling_reqs = get_baling_materials_required(production_plan_name)
    
    if not baling_reqs:
        return {"items_to_add": [], "baling_materials": []}
    
    # Consolidate materials across all finished items
    consolidated_materials = {}
    
    for seg_item, materials in baling_reqs.items():
        for material_code, qty_required in materials.items():
            if material_code not in consolidated_materials:
                consolidated_materials[material_code] = 0
            consolidated_materials[material_code] += qty_required
    
    items_to_add = []
    baling_materials = []
    
    # Prepare data for frontend
    for material_code, total_qty_required in consolidated_materials.items():
        # Check current stock
        warehouse_condition = ""
        if pp.for_warehouse:
            warehouse_condition = f"AND warehouse = '{pp.for_warehouse}'"
        
        actual_qty = frappe.db.sql(f"""
            SELECT SUM(actual_qty) 
            FROM `tabBin` 
            WHERE item_code = %s {warehouse_condition}
        """, (material_code,))[0][0] or 0
        
        # Calculate values
        total_qty_required = flt(total_qty_required, 3)
        actual_qty = flt(actual_qty, 3)
        shortage = max(0, total_qty_required - actual_qty)
        
        item_name = frappe.db.get_value("Item", material_code, "item_name")
        uom = frappe.db.get_value("Item", material_code, "stock_uom")
        
        # Add to baling materials list (for custom_baling_materials table)
        baling_materials.append({
            "item_code": material_code,
            "item_name": item_name,
            "required_qty": math.ceil(total_qty_required),
            "available_qty": actual_qty,
            "shortage_qty": shortage,
            "warehouse": pp.for_warehouse or "",
        })
        
        
        # (for mr_items table)
        if pp.ignore_existing_ordered_qty:
            items_to_add.append({
                "item_code": material_code,
                "item_name": item_name,
                "uom":uom,
                "quantity": math.ceil(total_qty_required),
                "warehouse": pp.for_warehouse or "",
                "material_request_type":"Purchase",
                "description": "Baling/Packing material",
                "required_bom_qty":total_qty_required
            })
        
        
        # Add to items list (for mr_items table) only if shortage
        if shortage > 0 and not pp.ignore_existing_ordered_qty:
            items_to_add.append({
                "item_code": material_code,
                "item_name": item_name,
                "uom":uom,
                "quantity": math.ceil(shortage),
                "warehouse": pp.for_warehouse or "",
                "material_request_type":"Purchase",
                "description": "Baling/Packing material",
                "required_bom_qty":total_qty_required
            })
    
    return {
        "items_to_add": items_to_add,
        "baling_materials": baling_materials
    }


@frappe.whitelist()
def check_mr_items_stock(production_plan_name):
    """
    Check stock availability for all mr_items
    Returns shortage summary
    """
    pp = frappe.get_doc("Production Plan", production_plan_name)
    
    if not pp.mr_items:
        return {"status": "no_data", "message": "No material request items"}
    
    shortage_count = 0
    
    for item in pp.mr_items:
        # Get current stock
        warehouse_condition = ""
        if item.warehouse:
            warehouse_condition = f"AND warehouse = '{item.warehouse}'"
        elif pp.warehouse:
            warehouse_condition = f"AND warehouse = '{pp.warehouse}'"
        
        actual_qty = frappe.db.sql(f"""
            SELECT SUM(actual_qty) 
            FROM `tabBin` 
            WHERE item_code = %s {warehouse_condition}
        """, (item.item_code,))[0][0] or 0
        
        actual_qty = flt(actual_qty, 3)
        required_qty = math.ceil(item.quantity)  # Changed from item.qty to item.quantity
        
        # Check if shortage exists
        if actual_qty < required_qty:
            shortage_count += 1
    
    return {
        "status": "checked",
        "has_shortage": shortage_count > 0,
        "shortage_count": shortage_count,
        "total_items": len(pp.mr_items)
    }


def get_baling_materials_required(production_plan_name):
    """
    Calculate materials required for baling based on segregated bags in production plan
    Returns: {segregated_item: {raw_material: qty_required}}
    """
    pp = frappe.get_doc("Production Plan", production_plan_name)
    
    baling_requirements = {}
    segregated_items = {}
    
    # Step 1: Identify segregated bags from po_items and their planned quantities
    for item in pp.po_items:
        item_group = frappe.db.get_value("Item", item.item_code, "item_group")
        
        if item_group == "segregated ad*star bags":
            if item.item_code not in segregated_items:
                segregated_items[item.item_code] = 0
            segregated_items[item.item_code] += item.planned_qty
    
    if not segregated_items:
        return {}
    
    # Step 2: Find BOMs where segregated bags are used as raw materials (for baling/packing)
    for seg_item, seg_qty in segregated_items.items():
        # Find BOMs that use this segregated item as raw material
        bom_items = frappe.get_all("BOM Item",
                                   filters={"item_code": seg_item},
                                   fields=["parent", "qty"])
        
        for bom_item in bom_items:
            # Get the BOM details
            bom = frappe.get_doc("BOM", bom_item.parent)
            
            # Skip if BOM is not active
            if bom.is_active != 1:
                continue
            
            # Calculate ratio
            bom_ratio = seg_qty / bom_item.qty
            
            # Get all raw materials from this BOM (except the segregated item itself)
            for raw_material in bom.items:
                # Don't include the segregated bag itself in baling materials
                if raw_material.item_code == seg_item:
                    continue
                
                # Calculate required qty
                required_qty = raw_material.qty * bom_ratio
                
                # Store in baling_requirements
                if seg_item not in baling_requirements:
                    baling_requirements[seg_item] = {}
                
                if raw_material.item_code not in baling_requirements[seg_item]:
                    baling_requirements[seg_item][raw_material.item_code] = 0
                
                baling_requirements[seg_item][raw_material.item_code] += required_qty
    
    return baling_requirements