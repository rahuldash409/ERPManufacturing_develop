frappe.ui.form.on("Material Request",{
    onload_post_render:function(frm){
        if(frm.doc.docstatus==1){
            frm.remove_custom_button("Purchase Order","Create")
            frm.add_custom_button("Procurement",()=>{
                frappe.model.open_mapped_doc({
			        		method: "erpnext.stock.doctype.material_request.material_request.make_purchase_order",
			        		frm: frm,
			        		run_link_triggers: true,
			    })   
            },"Create")
        }

    }
})