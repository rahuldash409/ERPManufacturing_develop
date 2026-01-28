frappe.ui.form.on("Sales Invoice",{
    refresh: async function(frm){
        let sum=0
        batches = []
        for (let item of frm.doc.items){
            if(frm.doc.docstatus == 1){
                if(item.serial_and_batch_bundle){
                    await frappe.call({
                        method:"frappe.client.get",
                        args:{
                            doctype:"Serial and Batch Bundle",
                            name:item.serial_and_batch_bundle
                        },
                        callback:(r)=>{
                            if(r.message){
                                r.message.entries.forEach((entry)=>{
                                    batches.push(entry.batch_no)
                                })
                            }
                        }
                    })
                    
                }
            }
        }

        for(let item of batches){
                        await frappe.call({
                            method:"frappe.client.get",
                            args:{
                                doctype:"Batch",
                                name:item
                            },
                            callback:(r)=>{
                                sum+=r.message.custom_segregated_item_qty || 0
                            }
                        })
                    }

        // if((sum>0) && (frm.doc.custom_total_segregated_bags_qty === 0)){
        //     frappe.call({
        //         method:"tcb_manufacturing_customizations.doc_events.sales_invoice.set_segregated_bags_qty",
        //         args:{
        //             docname:frm.doc.name,
        //             sum_qty:sum
        //         },
        //         callback:(r)=>{
        //             frm.refresh_field("custom_total_segregated_bags_qty")
        //         }
        //     })
        // }
    }
})