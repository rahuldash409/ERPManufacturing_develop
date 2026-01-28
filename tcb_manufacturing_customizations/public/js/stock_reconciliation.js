frappe.ui.form.on("Stock Reconciliation",{
    custom_sync_batches:function(frm,cdt,cdn){
        frm.doc.items.forEach(item=>{
            if(item.custom_sub_batch){
                frappe.call({
                    method:"frappe.client.get_list",
                    args:{
                        doctype:"Batch",
                        order_by:"creation ASC",
                        fields:["name"],
                        filters:{"item":item.item_code,"custom_sub_batch":item.custom_sub_batch},
                        limit_page_length:1
                    },
                    callback:(r)=>{
                        if(r.message && r.message.length>0){
                            frappe.model.set_value(item.doctype, item.name,"batch_no",r.message[0].name)
                        }
                    }
                })
            }
        })
    }
})