// frappe.ui.form.on("Delivery Estimate",{
//     get_sales_orders: function(frm) {
//     frappe.call({
//         method: "tcb_manufacturing_customizations.doc_events.delivery_estimate.fill_so",
//         args: {
//             docname: frm.doc.name
//         },
//         callback: function(r) {
//             if (r.message) {
//                 frm.reload_doc();
//             }
//         }
//     });
//     }

frappe.ui.form.on("Delivery Estimate", {
    get_sales_orders: async function(frm) {
        frm.clear_table("existing_sales_orders");
        // For Urgent flow
        let days_btw_today_and_request = 0 
        if (frm.urgent_dialog_values){

            const today_date = new Date();
            const requested_delivery_date = frm.urgent_dialog_values.requested_delivery_date
            days_btw_today_and_request = frappe.datetime.get_day_diff(requested_delivery_date,today_date );
            // console.log("0000000--------",days_btw_today_and_request);
                    
        }
        
        await frappe.call({
            method: "tcb_manufacturing_customizations.doc_events.delivery_estimate.get_sales_orders_data",
            callback: function(r) {
                
                if (r.message && r.message.length > 0) {
                    // console.log(r)
                    r.message.forEach(function(order) {
                        let child = frm.add_child("existing_sales_orders");
                        child.sales_order = order.sales_order;
                        child.linked_production_plan = order.linked_production_plan;
                        child.production_percentage = order.production_percentage;
                        child.customer = order.customer;
                        child.qty = order.qty;
                        child.delivery_date = order.delivery_date;
                        child.percentage_delivered = order.percentage_delivered;
                        child.requested_delivery_date = frappe.datetime.add_days(order.delivery_date,days_btw_today_and_request);
                    });
                    // console.log('order.delivery_date-=== ')
                    frm.refresh_field("existing_sales_orders");
                    frappe.show_alert({message: __("Sales Orders loaded successfully"), indicator: 'green'});
                    frm.save();
                    
                //     if(frm.urgent_dialog_values)
                //         {
                //             if (frm.urgent_dialog_values.item) {
                //         // console.log('ye chal rha hai -',frm.urgent_dialog_values)
                //         frappe.call({
                //             method: "tcb_manufacturing_customizations.doc_events.delivery_estimate.set_bom",
                //             args: {
                //                 docname: frm.doc.name,
                //                 item: frm.doc.item_to_deliver,
                //                 document: frm.doc
                //             },
                //             callback: (r) => {
                //                 if (!r.message){
                //                     frappe.throw('No BOM found for this Item.')
                //                 }
                //                 else{

                //                     frm.set_value("bom", r.message)
                //                     frm.save();
                //                 }
                                
                //             }
                //         })
                //     }
                // }
                //     else {
                //     }
                } else {
                    frappe.msgprint(__("No pending sales orders found"));
                }
            }
        });
    
    }
,
    refresh:function(frm){
        frm.fields_dict["workstation_specifications"].grid.get_field("workstation").get_query = function(doc, cdt, cdn) {
        let row = locals[cdt][cdn];
            if (row.item) {
                return {
                    query: "tcb_manufacturing_customizations.doc_events.delivery_estimate.workstation_query_for_item",
                    filters: {
                        "item_code": row.item
                    }
                };
            }
            return {
                filters: {"name": ["=", ""]}
            };
        };

        // frm.fields_dict["employee_details"].grid.get_fields("employee").get_query = function(doc,cdt,cdn){
        //     let response
        //     frappe.call({
        //         method:"tcb_manufacturing_customizations.doc_events.delivery_estimate.check_employees",
        //         callback:(r)=>{
        //             console.log(r.message)
        //             response = r.message
        //         }
        //     })
        //     return{
        //         filters:{
        //             "name":["not in",response]
        //         }
        //     }
        // }
        // frappe.call({
        //     method:"tcb_manufacturing_customizations.doc_events.delivery_estimate.check_employees",
        //     callback:(r)=>{
        //         if(r.message){
        //             // frm.emp_unv_list = Object.keys(r.message)
        //             frm.emp_unv_list = r.message

        //             frm.fields_dict["employee_details"].grid.get_field("employee").get_query=function(doc,cdt,cdn){
        //                 return{
        //                     filters:[
        //                         // ["Employee","name","not in",frm.emp_unv_list]
        //                     ]
        //                 }
        //             }
        //         }
        //     }
        // })
    },
    // SET BOM on setting item
    item_to_deliver:async function(frm){
            // console.log('ented in item delver ation')
            let item = frm.doc.item_to_deliver;
            // console.log('----this is hte item -',item)
            if (item) {
            // console.log('----this is hte item -',item)
                try {
                    // get  BOM for this item
                    let boms = await frappe.db.get_list('BOM', {
                        filters: {
                            item: item,
                            is_default: 1
                        },
                        fields: ['name'],
                        order_by: 'modified desc',
                        limit: 1
                    });

                    if (boms && boms.length > 0) {
                        frm.set_value('bom', boms[0].name);
                    } else {
                        frappe.msgprint(__('No default BOM found for this item.'));
                        frm.set_value('bom', null);
                        frm.set_value('item_to_deliver', null);
                    }
                } catch (err) {
                    console.error("Error fetching BOM:", err);
                    frappe.msgprint(__('Error fetching BOM.'));
                }
            }
        // }
    // },
        // frappe.call({
        //     method:"tcb_manufacturing_customizations.doc_events.delivery_estimate.set_bom",
        //     args:{
        //         docname : frm.doc.name,
        //         item:frm.doc.item_to_deliver
        //     },
        //     callback:(r)=>{
        //         frm.set_value("bom",r.message)
        //     }
        // })
    },

    calculate_raw_materials:function(frm){
        // console.log("yeeeeeey",frm)
        if (frm.doc.qty_to_deliver <= 0 ){
            frappe.throw("Please Enter The Quantity to Deliver!");
        }
        frappe.call({
            method:"tcb_manufacturing_customizations.doc_events.delivery_estimate.calculate_bom",
            args:{
                client_doc:frm.doc
            },
            callback:function(r){
                frm.set_value("table_ilpb",r.message.table_ilpb);
                // console.log("here is the table lltb- ",frm.doc.table_ilpb)
                frm.refresh_field('table_ilpb');
                let item_qty_map = {};
        for (const row of frm.doc.table_ilpb) {
            // console.log('here is the row - ',row)
            if (!item_qty_map[row.item_code]) {
                item_qty_map[row.item_code] = 0;
            }
            item_qty_map[row.item_code] += row.qty;
        }

        // SET TO 0 SO THAT IT WONT ACCUMULATE QTY
        for (let row of frm.doc.warehouse_wise_stock) {
        row.required_qty = 0;
        }

        for (const item_code in item_qty_map) {
            let existing_row = frm.doc.warehouse_wise_stock.find(i => i.item === item_code);
            
            if (existing_row) {
                existing_row.required_qty += item_qty_map[item_code];
            } else {
                let child = frm.add_child("warehouse_wise_stock");
                child.item = item_code;
                child.required_qty = item_qty_map[item_code];
                // console.log("here is the child requreted qty-",child.required_qty)

            }
        }
        frm.refresh_field("warehouse_wise_stock");
        frm.save();
    }
});

        
    },
    validate: async function(frm) {
    
        
        


        // SET LEAD TIME
        // -Planning to take it to server side
        // if(frm.doc.warehouse_wise_stock){
        //     let lead_time = 0
        //     for(row of frm.doc.warehouse_wise_stock){
        //         if(row.deficit_qty){
        //             await frappe.db.get_doc("Item",row.item)
        //             .then(item=>{
        //                 if(item.lead_time_days && item.lead_time_days>lead_time){
        //                 lead_time = item.lead_time_days
        //                 }
        //             })
        //         }
        //     }
        //     if (lead_time){
        //         frm.set_value("procurement_lead_time_taken_in_days",lead_time)
        //         frm.refresh_field("procurement_lead_time_taken_in_days")
        //     }
        // }
        
        // CALCULATE BAGS PER MINUTE
        if(frm.doc.bag_width_bw && frm.doc.bottom_width_bow && frm.doc.machine && !frm.doc.bags_per_minute){
            let mach = await frappe.db.get_doc("Machine",frm.doc.machine)
            for(let item of mach.machine_output){
                if(item.bag_width == frm.doc.bag_width_bw && item.bottom_width == frm.doc.bottom_width_bow){
                    frm.set_value("bags_per_minute",item.capacity)
                    break
                }
                frm.refresh_field("bags_per_minute")
            }
        }

        // DAYS TO COMPLETE THE ORDER
        setTimeout(()=>{
            if(frm.doc.bags_per_minute && frm.doc.qty_to_deliver){
                let bags_per_hour = frm.doc.bags_per_minute*60
                let workday = 8
                let days_taken = (frm.doc.qty_to_deliver/bags_per_hour)/workday
                frm.set_value("days_to_complete_the_order",days_taken)
                frm.set_value("hours_to_complete_the_order",frm.doc.qty_to_deliver/bags_per_hour)
                frm.refresh_field("days_to_complete_the_order")
            }
        })
        
    },
    check_stock_availability:function(frm){
        // console.log('here is the lengh of ware stock items -',frm.doc.warehouse_wise_stock.length)
        let total_rows = frm.doc.warehouse_wise_stock.length;
        let row_set_count = 0;
        frm.doc.warehouse_wise_stock.forEach(item=>{
            
            frappe.call({
                method:'frappe.client.get_list',
                args:{
                    doctype:"Bin",
                    filters:{"item_code":item.item},
                    fields:["actual_qty","warehouse","reserved_qty_for_production","reserved_qty_for_sub_contract",
                            "reserved_qty_for_production_plan","reserved_stock","reserved_qty"
                    ],
                    limit_page_length:50
                },

                callback:(r)=>{
                    let sum = 0
                    let wh_details = ""
                    let reserved_qty_sum =0;
                    r.message.forEach(row=>{
                        sum+=row.actual_qty;
                        wh_details += (row.warehouse.replace(" - APUI","") + " - " + row.actual_qty+","+ "\n");
                        reserved_qty_sum = (row.reserved_qty>0?row.reserved_qty:0) + 
                        (row.reserved_qty_for_production >0?row.reserved_qty_for_production:0) + 
                        (row.reserved_qty_for_sub_contract >0?row.reserved_qty_for_sub_contract:0) + 
                        (row.reserved_qty_for_production_plan >0?row.reserved_qty_for_production_plan:0) + 
                        (row.reserved_stock  >0?row.reserved_stock:0);
                    })
                    frappe.model.set_value(item.doctype, item.name, "available_qty", sum);
                    frappe.model.set_value(item.doctype, item.name, "warehouse_details",wh_details);
                    frappe.model.set_value(item.doctype, item.name, "deficit_qty",item.required_qty>sum?item.required_qty-sum:0);
                    frappe.model.set_value(item.doctype, item.name, "reserved_qty", reserved_qty_sum>0?reserved_qty_sum:0);
                    frappe.model.set_value(item.doctype, item.name, "available_qtyafter_deduction_reserved", sum-reserved_qty_sum);
                    frappe.model.set_value(item.doctype, item.name, "net_deficit_qty", (item.required_qty < (sum-reserved_qty_sum)?0:(item.required_qty - (sum-reserved_qty_sum))));
                    frm.refresh_field("warehouse_wise_stock");
                    row_set_count++;
                    if (row_set_count === total_rows) {
                    frm.save();
                }
                }
            })
        })
    },
    calculate_lead_time:function(frm){
        frappe.call({
            method:"tcb_manufacturing_customizations.doc_events.delivery_estimate.calculate_lead_time",
            args:{
                docname:frm.doc.name
            },
            // callback:(r)=>{
            //     if(r.message=="True"){
                    
            //     }
            // }
        })
    },

    // CALCULATE PROCUREMETN LEAD TIME
    calculate_procurement_lead_time:function(frm){
        frappe.call({
            method:"tcb_manufacturing_customizations.doc_events.delivery_estimate.calculate_procurement_lead_time",
            args:{
                docname:frm.doc.name
            }
        })
    },
    
    get_item_wise_workstation: function(frm) {
        frappe.call({
            method: "tcb_manufacturing_customizations.doc_events.delivery_estimate.get_item_wise_workstation",
            args: {
                docname: frm.doc.name
            },
        });
    frm.refresh_field("workstation_specifications");
},
    calculate_delivery_date:function(frm){
        frappe.call({
            method:"tcb_manufacturing_customizations.doc_events.delivery_estimate.calculate_delivery_date",
            args:{
                docname:frm.doc.name
            }
        })
    },
    // get_employees_list:function(frm){
    // frappe.call({
    //         method:"tcb_manufacturing_customizations.doc_events.delivery_estimate.get_employees_jobwise",
    //         args:{
    //             docname:frm.doc.name
    //         }
    //     })
    // },


    get_employee_leave_list:function(frm){
    frappe.call({
            method:"tcb_manufacturing_customizations.doc_events.delivery_estimate.get_employee_leave_list",
            args:{
                docname:frm.doc.name
            }
        })
    },
    // CALCULATE PRODUCTION DETAILS
    calculate_production_details:function(frm){
        frappe.call({
            method:"tcb_manufacturing_customizations.doc_events.delivery_estimate.calc_prod_details",
            args:{
                docname : frm.doc.name
            }
        })
    }
})