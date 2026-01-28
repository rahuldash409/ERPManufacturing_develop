frappe.ui.form.on("Job Card",{


    // Function for Complete job button
    complete_job: function (frm, status, completed_qty) {
		const args = {
			job_card_id: frm.doc.name,
			complete_time: frappe.datetime.now_datetime(),
			status: status,
			completed_qty: completed_qty,
		};
		frm.events.make_time_log(frm, args);
	},
    make_time_log: function (frm, args) {
		frm.events.update_sub_operation(frm, args);

		frappe.call({
			method: "erpnext.manufacturing.doctype.job_card.job_card.make_time_log",
			args: {
				args: args,
			},
			freeze: true,
			callback: function () {
				frm.reload_doc();
				frm.trigger("make_dashboard");
			},
		});
	},
    update_sub_operation: function (frm, args) {
		if (frm.doc.sub_operations && frm.doc.sub_operations.length) {
			let sub_operations = frm.doc.sub_operations.filter((d) => d.status != "Complete");
			if (sub_operations && sub_operations.length) {
				args["sub_operation"] = sub_operations[0].sub_operation;
			}
		}
	},

    refresh: function(frm) {
        // Remove material request and create button
        frm.remove_custom_button("Material Request","Create")

        // Toggle Bales Plan visibility based on production item group
        toggle_bales_plan_visibility(frm);

        // If the checkbox for reload is there when the refersh event is triggered,, uncheck it and trigger a hard reload

        frappe.db.get_value(
            "Job Card",frm.doc.name,"custom_need_document_refresh").then((r)=>{
                if(r.message?.custom_need_document_refresh){
                    frappe.db.set_value("Job Card",frm.doc.name,"custom_need_document_refresh",0).then(()=>{
                        window.location.reload()
                    })
                }
        })

        // console.log("checking if form is dirty")
        // if(frm.is_dirty()){
        //     console.log("Form is dirty")
        //     frm.save()
        // }

        
       frappe.db.get_value(frm.doc.doctype, frm.doc.name, "custom_stock_entry_reference", (resp)=>{
        // frappe.msgprint(resp.custom_stock_entry_reference)
        let stock_entry_reference = frm.doc.custom_stock_entry_reference;
        if(stock_entry_reference != resp.custom_stock_entry_reference){
            frm.doc.custom_stock_entry_reference = resp.custom_stock_entry_reference;
            frm.set_value("custom_stock_entry_reference", resp.custom_stock_entry_reference)
            frm.doc.__unsaved = 0
            frm.refresh()
        }
        
       })

        // if (frm.doc.total_completed_qty && frm.doc.for_quantity !== frm.doc.total_completed_qty && !frm.doc.custom_process_loss) {
        //     setTimeout(() => {
        //         frm.set_value("for_quantity", frm.doc.total_completed_qty);
        //         frm.save();
        //     }, 400);
        // }

        if(frm.doc.status!=="Work In Progress"){
            frm.set_df_property("custom_material_consumption","read_only",1)
            frm.set_df_property("custom_total_material_consumed","read_only",1)
            frm.set_df_property("custom_material_consumed_after_deducting_wastage","read_only",1)
            frm.set_df_property("custom_total_material_wasted","read_only",1)
            frm.set_df_property("custom_process_loss","read_only",1)
            frm.set_df_property("custom_total_material_wasted_lbs","read_only",1)
        }


        frm.refresh_field("custom_material_consumption")
        frm.refresh_field("custom_stock_entry_reference")
        // SETTING UP DATA TO TRANSFER TO STOCK ENTRY
        if (frm.doc.docstatus == 1 && !frm.doc.custom_stock_entry_reference) {
            raw_mats = {}

            let whichtable = [];

            switch (frm.doc.operation) {
                case "Printing":
                case "Segregation":
                    whichtable = frm.doc.custom_material_consumption || [];
                    break;
            
                case "Slitting":
                    whichtable = frm.doc.custom_material_consumption_slitec || [];
                    break;
            
                case "Bag Manufacturing":
                    whichtable = frm.doc.custom_material_consumption_adstar || [];
                    break;
                
                case "Packaging":
                    whichtable = frm.doc.custom_bales_plan || [];
                    break;
            
                default:
                    whichtable = [];
            }

            
            if (whichtable.length>0){
                for(let row of whichtable){

                if(frm.doc.operation == "Packaging"){
                    data = {
                        "from_warehouse":row.warehouse,
                        "item":row.packaging_item,
                        "sub_batch":row.sub_batch,
                        "qty":parseFloat(row.batch_qty_used),
                        "batch":row.batch_no,
                        "machine_consumption":0,
                        "roll_cutlengths":0,
                        "manufactured_bags":0,
                        "bale_n":row.bale_number || ""
                    }   
                }
                else{
                    data = {
                        "from_warehouse":row.warehouse,
                        "item":row.item,
                        "sub_batch":row.sub_batch,
                        "qty":parseFloat(row.qty),
                        "batch":row.batch,
                        "machine_consumption":parseFloat(row.material_consumed - row.wastage_qty_in_item_uom),
                        "roll_cutlengths":row.roll_cut_lengths,
                        "manufactured_bags":row.manufactured_qty
                    }   
                }

                if( !raw_mats[row.item]){   
                    raw_mats[row.item]=[]
                }
                raw_mats[row.item].push(data)
                }
            }

            frappe.confirm(`Create Stock Entry for <b>${frm.doc.total_completed_qty}</b> Quantity of <b>${frm.doc.production_item}</b>?`, () => {
                    make_se_from_jc(
                        frm.doc.work_order,
                        "Manufacture",
                        frm.doc.total_completed_qty,
                        frm.doc.name,
                        raw_mats,
                        frm.doc.custom_total_material_wasted_lbs,
                        frm.doc.scrap_items?.filter((item)=>!item.custom_from_bom)
                    );
            });
        }
        
        // ASK THE USER TO CHANGE THE QTY TO MANUFACTURE IN JC
        if(frm.doc.status === "Work In Progress" && frm.doc.docstatus!=2 && frm.doc.custom_material_consumed_after_deducting_wastage  && parseFloat(frm.doc.for_quantity)!=parseFloat(frm.doc.custom_material_consumed_after_deducting_wastage)){
                frappe.confirm(`${frm.doc.item_name}'s <b>previous Target Qty was <b>${(frm.doc.for_quantity)}</b>. Set it to <b>${((parseFloat(frm.doc.custom_material_consumed_after_deducting_wastage?.toFixed(3))))} </b> as now produced?`,async ()=>{
                await frappe.db.set_value("Job Card",frm.doc.name,"for_quantity",parseFloat(frm.doc.custom_material_consumed_after_deducting_wastage))
                .then(()=>{
                    frm.reload_doc()
                })
                await frappe.db.set_value("Job Card",frm.doc.name,"transferred_qty",parseFloat(frm.doc.custom_material_consumed_after_deducting_wastage))
                .then(()=>{
                    frm.reload_doc()
                })
            })
        }


        // Modify the complete job button to enter the right qty
        if(frm.doc.status=="Material Transferred" && frm.doc.docstatus==0 && frm.doc.time_logs.length<1){
            frm.remove_custom_button("Start Job")
            frm.add_custom_button(__("Start Job"), () => {
				if ((frm.doc.employee && !frm.doc.employee.length) || !frm.doc.employee) {
					frappe.prompt(
						{
							fieldtype: "Table MultiSelect",
							label: __("Select Employees"),
							options: "Job Card Time Log",
							fieldname: "employees",
						},
						(d) => {
							frm.events.start_job(frm, "Work In Progress", d.employees);
						},
						__("Assign Job to Employee")
					);
				} else {
					frm.events.start_job(frm, "Work In Progress", frm.doc.employee);
				}
                    frm.set_df_property("custom_material_consumption","read_only",0)
                    frm.set_df_property("custom_total_material_consumed","read_only",0)
                    frm.set_df_property("custom_material_consumed_after_deducting_wastage","read_only",0)
                    frm.set_df_property("custom_total_material_wasted","read_only",0)
                    frm.set_df_property("custom_process_loss","read_only",0)
                    frm.set_df_property("custom_total_material_wasted_lbs","read_only",0)
			}).addClass("btn-primary");
        }

        // EARLIER I HAD ADDED A CONDITION FOR PROCESS LOSS HERE.. WHY THO?
        if(frm.doc.docstatus==0){
            if(frm.doc.status == "Work In Progress"){
                frm.remove_custom_button("Complete Job")
                frm.add_custom_button("Complete Job", ()=>{
                    var sub_operations = frm.doc.sub_operations;
			    	let set_qty = true;
			    	if (sub_operations && sub_operations.length > 1) {
			    		set_qty = false;
			    		let last_op_row = sub_operations[sub_operations.length - 2];
			    		if (last_op_row.status == "Complete") {
			    			set_qty = true;
			    		}
			    	}
			    	if (set_qty) {
			    		frappe.prompt(
			    			{
			    				fieldtype: "Float",
			    				label: __("Completed Quantity"),
			    				fieldname: "qty",
			    				default: frm.doc.custom_material_consumed_after_deducting_wastage
			    			},
			    			(data) => {
			    				frm.events.complete_job(frm, "Complete", data.qty);
                                
			    			},
			    			__("Enter Value")
			    		);
			    	} else {
			    		frm.events.complete_job(frm, "Complete", 0.0);
			    	}
                
			    }).addClass("btn-primary");
                if(frm.doc.total_completed_qty){
                    frm.remove_custom_button("Complete Job")
                    frm.remove_custom_button("Start Job")
                    frm.remove_custom_button("Material Request","Create")
                    frm.remove_custom_button("Material Transfer","Create")
                }
            }
        }



        

        // FETCH THE MATERIALS FOR CONSUMPTION IN THE JOB CARD TABLE--------------METHOD COPIED FROM SE-----------------------
        if(frm.doc.work_order){
            if (
            frm.doc.docstatus == 0 && frm.doc.work_order) {
            // frm.set_df_property("custom_sync_sub_batch_qty","hidden",1)
    
            frappe.call({
                method:
                    "tcb_manufacturing_customizations.doc_events.stock_entry.get_unconsumed_transfers",
                args: {
                  work_order: frm.doc.work_order,
                  opn :frm.doc.operation,
                //   current_stock_entry: frm.doc.name || null,
                },
                callback: (r) => {
                  if (r.message && r.message.length > 0) {
                    if ((frm.doc.operation === "Printing" || frm.doc.operation === "Segregation") && frm.doc.custom_material_consumption == 0){

                        r.message.forEach((row) => {
                            if(!row.item_code.toLowerCase().includes("ink") && !row.item_code.toLowerCase().includes("solvent")){
                                let list = frm.add_child("custom_material_consumption");
                                list.operation = frm.doc.operation;
                                list.workstation = frm.doc.workstation;
                                list.item = row.item_code;
                                list.qty = row.available_qty;
                                list.sub_batch = row.sub_batch || "";
                                list.batch = row.batch_no;
                                list.warehouse = row.warehouse;
                            }
                        });
                        frm.refresh_field("custom_material_consumption");
                    }
                    if (frm.doc.operation === "Slitting" && frm.doc.custom_material_consumption_slitec == 0){

                        r.message.forEach((row) => {
                            let list = frm.add_child("custom_material_consumption_slitec");
                            list.operation = frm.doc.operation;
                            list.workstation = frm.doc.workstation;
                            list.item = row.item_code;
                            list.qty = row.available_qty;
                            list.sub_batch = row.sub_batch || "";
                            list.batch = row.batch_no;
                            list.warehouse = row.warehouse;
                        });
                        frm.refresh_field("custom_material_consumption_slitec");
                    }
                    if (frm.doc.operation === "Bag Manufacturing" && frm.doc.custom_material_consumption_adstar == 0){

                        r.message.forEach((row) => {
                            let list = frm.add_child("custom_material_consumption_adstar");
                            list.operation = frm.doc.operation;
                            list.workstation = frm.doc.workstation;
                            list.item = row.item_code;
                            list.qty = row.available_qty;
                            list.sub_batch = row.sub_batch || "";
                            list.batch = row.batch_no;
                            list.warehouse = row.warehouse;
                        });
                        frm.refresh_field("custom_material_consumption_adstar");
                    }
                  }
                },      
            });
        }
        }


        
        

    },


    // MULTIPLE QCS AGAINST A SINGLE JC
    onload:function(frm){
        frm.refresh_field("custom_stock_entry_reference")
        // set the property of the field named custom_quality_inspections to read only
        frm.set_df_property("custom_quality_inspections","read_only",1)
        settings = frappe.db.get_single_value("Manufacturing Settings","allow_multiple_qc")
        .then(value=>{
            if (value){
                frappe.call({
                    method:"tcb_manufacturing_customizations.doc_events.job_card.get_quality_inspections",
                    args:{
                        jc : frm.doc.name
                    }
                })
            }
        })
    },

    // GET SCRAP ITEMS IN THE JC SCRAP SECTION
    onload_post_render:function(frm){

        frm.refresh_field("custom_stock_entry_reference")
        if(frm.doc.bom_no && frm.doc.docstatus==0 && frm.doc.scrap_items.length < 1){
                frappe.call({
                    method:"frappe.client.get",
                    args:{
                        doctype:"BOM",
                        name:frm.doc.bom_no
                    },
                    callback:(r)=>{
                        let bom = r.message
                        if(bom.scrap_items){
                            frm.clear_table("scrap_items")

                            bom.scrap_items.forEach(item=>{
                                let row = frm.add_child("scrap_items")
                                row.item_code = item.item_code
                                row.item_name = item.item_name
                                row.stock_qty = item.stock_qty
                                row.custom_from_bom = 1
                            })
                            frm.refresh_field("scrap_items")
                        }
                    }
                })
            }



        
        // Make the assign patch and valve calculations button conditional
        if(frm.doc.operation!=="Bag Manufacturing"){
            frm.set_df_property("custom_assign_patch_and_valve_quantities","hidden",1)
        }

        // Check how much each qty is needed for ad*star bags
    },

    validate:function(frm){







        // 1ST CASE OF SEGREGATION AND PRINTING

        // Dynamically set values under the material consumption table in job card
        if(frm.doc.custom_material_consumption.length>0){
            let sum_of_consumed = 0
            let wasted_item_uom_qty = 0
            let process_losss = 0
            let wastage_lbs = 0



            frm.doc.custom_material_consumption.forEach((row)=>{

              
                if(row.material_consumed && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    sum_of_consumed+=row.material_consumed
                }
                if (row.wastage_qty_in_item_uom && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    wasted_item_uom_qty+=row.wastage_qty_in_item_uom
                }
                if(row.process_loss && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    process_losss+= row.process_loss
                }
                if(row.wastage_qty && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    wastage_lbs+= row.wastage_qty
                }
            
                
            })
            if(frm.doc.custom_total_material_consumed!==sum_of_consumed){
                // console.log("check 1")
                frm.set_value("custom_total_material_consumed",sum_of_consumed)
            }
            if(frm.doc.custom_total_material_wasted!==wasted_item_uom_qty){
                // console.log("check 2")
                frm.set_value("custom_total_material_wasted",wasted_item_uom_qty)
            }
            if(frm.doc.custom_process_loss!==process_losss){
                // console.log("check 3")
                frm.set_value("custom_process_loss",process_losss)
            }
            if(frm.doc.custom_total_material_wasted_lbs!==wastage_lbs){
                // console.log("check 4")
                frm.set_value("custom_total_material_wasted_lbs",wastage_lbs)
            }

        }

        // SET FINISHED GOODS FOR PRINTING BAGS
        if(frm.doc.custom_total_material_consumed && frm.doc.operation==="Printing"){
            frm.set_value("custom_material_consumed_after_deducting_wastage",parseFloat(frm.doc.custom_total_material_consumed) - parseFloat(frm.doc.custom_total_material_wasted || 0))
        }


        if (frm.doc.custom_total_material_wasted_lbs) {
            
            // Loop through all scrap items
            frm.doc.scrap_items.forEach(row => {
                if (row.custom_item_group && 
                    row.custom_item_group.toLowerCase() === "wastage") {
                    
                    frappe.model.set_value( row.doctype,  row.name,  "stock_qty",  frm.doc.custom_total_material_wasted_lbs);
                    frappe.model.set_value( row.doctype,  row.name,  "custom_from_bom",  0);
                }
            });
            
            frm.refresh_field("scrap_items");
        }


          // SET FINISHED GOODS FOR Segregated BAGS
        if(frm.doc.custom_total_material_consumed && frm.doc.operation==="Segregation"){
            frm.set_value("custom_material_consumed_after_deducting_wastage",parseFloat(frm.doc.custom_total_material_consumed) - parseFloat(frm.doc.custom_total_material_wasted || 0))
        }







        // 2ND CASE OF BAG MANUFACTURING

        if(frm.doc.custom_material_consumption_adstar.length>0){
            let sum_of_consumed = 0
            let wasted_item_uom_qty = 0
            let wastage_lbs = 0
            let pt_mb_qty = 0


            frm.doc.custom_material_consumption_adstar.forEach((row)=>{

                if(row.manufactured_qty && row.item_name?.includes("main") && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    pt_mb_qty+=row.manufactured_qty
                    // console.log("main body qty is",pt_mb_qty)
                }
                if(row.material_consumed && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    sum_of_consumed+=row.material_consumed
                }
                if (row.wastage_qty_in_item_uom && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    wasted_item_uom_qty+=row.wastage_qty_in_item_uom
                }
                // if(row.process_loss && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                //     process_losss+= row.process_loss
                // }
                if(row.wastage_qty && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    wastage_lbs+= row.wastage_qty
                }
                // if(row.slitted_good_qty && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                //     slitted_qty+=row.slitted_good_qty
                // }
                
            })
            if(frm.doc.custom_total_material_consumed!==sum_of_consumed){
                // console.log("check 1")
                frm.set_value("custom_total_material_consumed",sum_of_consumed)
            }
            if(frm.doc.custom_total_material_wasted!==wasted_item_uom_qty){
                // console.log("check 2")
                frm.set_value("custom_total_material_wasted",wasted_item_uom_qty)
            }
            // if(frm.doc.custom_process_loss!==process_losss){
            //     // console.log("check 3")
            //     frm.set_value("custom_process_loss",process_losss)
            // }
            if(frm.doc.custom_total_material_wasted_lbs!==wastage_lbs){
                // console.log("check 4")
                frm.set_value("custom_total_material_wasted_lbs",wastage_lbs)
            }


        }


        // // SET FINISHED GOODS FOR AD*STAR BAGS
        // // console.log("checking for adstar total")
        if(frm.doc.operation==="Bag Manufacturing" && frm.doc.custom_material_consumption_adstar.length>0){
            let adstar_sum = 0
            frm.doc.custom_material_consumption_adstar.forEach((row)=>{
                if(row.item_name?.toLowerCase().includes("body") && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    adstar_sum += Math.round(row.manufactured_qty)
                }
            })
            if(adstar_sum!=frm.doc.custom_material_consumed_after_deducting_wastage){
        
                frm.set_value("custom_material_consumed_after_deducting_wastage",Math.round(adstar_sum))
            }

        }


      






        // 3RD CASE OF SLITTING

        // Dynamically set values under the material consumption table in job card
        if(frm.doc.custom_material_consumption_slitec.length>0){
            let sum_of_consumed = 0
            let wasted_item_uom_qty = 0
            let process_losss = 0
            let wastage_lbs = 0
            let slitted_qty = 0
            let pt_mb_qty = 0


            frm.doc.custom_material_consumption_slitec.forEach((row)=>{

                if(row.material_consumed && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    sum_of_consumed+=row.material_consumed
                }
                if (row.wastage_qty_in_item_uom && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    wasted_item_uom_qty+=row.wastage_qty_in_item_uom
                }
                if(row.process_loss && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    process_losss+= row.process_loss
                }
                if(row.wastage_qty && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    wastage_lbs+= row.wastage_qty
                }
                if(row.slitted_good_qty && !row.item?.toLowerCase().includes("ink") && !row.item?.toLowerCase().includes("solvent")){
                    slitted_qty+=row.slitted_good_qty
                }
                
            })
            if(frm.doc.custom_total_material_consumed!==sum_of_consumed){
                // console.log("check 1")
                frm.set_value("custom_total_material_consumed",sum_of_consumed)
            }
            if(frm.doc.custom_total_material_wasted!==wasted_item_uom_qty){
                // console.log("check 2")
                frm.set_value("custom_total_material_wasted",wasted_item_uom_qty)
            }
            if(frm.doc.custom_process_loss!==process_losss){
                // console.log("check 3")
                frm.set_value("custom_process_loss",process_losss)
            }
            if(frm.doc.custom_total_material_wasted_lbs!==wastage_lbs){
                // console.log("check 4")
                frm.set_value("custom_total_material_wasted_lbs",wastage_lbs)
            }

            // SET FINISHED GOOD FOR SLITEC ENTRY
            if(frm.doc.operation ==="Slitting" && slitted_qty){
                // console.log("check 5")
                frm.set_value("custom_material_consumed_after_deducting_wastage",slitted_qty)
            }

        }




        // 4TH CASE BALING
        if(frm.doc.custom_bales_plan){
            let sum = 0
            frm.doc.custom_bales_plan.forEach((row)=>{
                sum+= row.batch_qty_used
            })
            if(sum) frm.set_value("custom_material_consumed_after_deducting_wastage",sum)
        }
        
    },

    custom_refetch_transferred_items:function(frm){
        frm.clear_table("custom_material_consumption")
        frm.clear_table("custom_material_consumption_slitec")
        frm.clear_table("custom_material_consumption_adstar")
        frm.clear_table("custom_packaging_materials")
        frm.reload_doc()
    },


    custom_assign_patch_and_valve_quantities: function(frm) {
    if ((frm.doc.custom_material_consumed_after_deducting_wastage || frm.doc.for_quantity) && 
        frm.doc.operation === "Bag Manufacturing" && 
        frm.doc.custom_material_consumption_adstar) {

        frappe.call({
            method: "tcb_manufacturing_customizations.doc_events.job_card.get_fg_to_rm_ratio",
            args: {
                bom_no: frm.doc.bom_no
            },
            callback: (r) => {
                const [mb_ratio, sl_pa_ratio, sl_va_ratio] = r.message;
                
                // Calculate total manufactured bags from Main Body batches
                let total_bags_manufactured = 0;
                frm.doc.custom_material_consumption_adstar.forEach(row => {
                    if (row.item_name?.toLowerCase().includes("body") && row.manufactured_qty) {
                        total_bags_manufactured += row.manufactured_qty;
                    }
                });


                // Calculate requirements based on actual manufactured quantity
                let pa_req = sl_pa_ratio ? total_bags_manufactured / sl_pa_ratio : 0;
                let va_req = sl_va_ratio ? total_bags_manufactured / sl_va_ratio : 0;

               

                // Step 1: Collect patch and valve rows, deduct fully used batches
                let patch_rows = [];
                let valve_rows = [];

                frm.doc.custom_material_consumption_adstar.forEach(row => {
                    if (row.item_name?.toLowerCase().includes("patch")) {
                        patch_rows.push(row);
                        if (row.batch_fully_used==="Yes") {
                            // let consume = row.qty;
                            // OLD FUNCTIONALITY WHERE DISTRIBUTION WAS ACCORDING TO REQUIRED QTY
                            let consume = Math.min(pa_req, row.qty);
                            frappe.model.set_value(row.doctype, row.name, "material_consumed", row.qty);
                            pa_req -= consume;
                        }
                    }
                    
                    if (row.item_name?.toLowerCase().includes("valve")) {
                        valve_rows.push(row);
                        if (row.batch_fully_used==="Yes") {
                            // let consume = row.qty;
                            // OLD FUNCTIONALITY WHERE DISTRIBUTION WAS ACCORDING TO REQUIRED QTY
                            let consume = Math.min(va_req, row.qty);
                            frappe.model.set_value(row.doctype, row.name, "material_consumed", row.qty);
                            va_req -= consume;
                        }
                    }
                });

                // Step 2: Distribute remaining equally among non-fully-used batches
                let remaining_patch_rows = patch_rows.filter(r => r.batch_fully_used==="No");
                let remaining_valve_rows = valve_rows.filter(r => r.batch_fully_used==="No");

                if (pa_req > 0 && remaining_patch_rows.length > 0) {
                    let equal_pa = pa_req / remaining_patch_rows.length;
                    remaining_patch_rows.forEach(row => {
                        let consume = Math.min(equal_pa, row.qty);
                        frappe.model.set_value(row.doctype, row.name, "material_consumed", Math.round(consume));
                    });
                }

                if (va_req > 0 && remaining_valve_rows.length > 0) {
                    let equal_va = va_req / remaining_valve_rows.length;
                    remaining_valve_rows.forEach(row => {
                        let consume = Math.min(equal_va, row.qty);
                        frappe.model.set_value(row.doctype, row.name, "material_consumed", Math.round(consume));
                    });
                }

                frm.refresh_field("custom_material_consumption_adstar");
                frappe.show_alert({
                    message: __(`Assigned based on ${total_bags_manufactured} bags manufactured`), 
                    indicator: "green"
                });
            }
        });
    }
}


})

// Make stock entry from submitted job card
function make_se_from_jc (wo,purpose,qty,jc_name,raw_mats,wastage,wastage_table){
    frappe.xcall("erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry",
        {
            work_order_id:wo,
            purpose:purpose,
            qty:qty,
            mat_entry_type:"Manufacture",
            jc_list:jc_name,
            raw_materials:JSON.stringify(raw_mats),
            wastage:wastage,
            wastage_items:wastage_table

    }).then((res)=>{
        frappe.model.sync(res)
        frappe.set_route("Form",res.doctype,res.name)
    })
}

// helper function to get details from work order
async function get_wo_details(frm){
    let doc = await frappe.db.get_doc("Work Order",frm.doc.work_order)

    let qty = doc.qty || 0
    let req_qty = 0
    for(let item of doc.required_items){
        if((item.item_name?.toLowerCase().includes("patch")) || item.item_name?.toLowerCase().includes("valve") || item.item_name?.toLowerCase().includes("flat")){
            req_qty+=item.required_qty || 0
        }
    }
    // console.log(req_qty)
    // console.log(qty)
    return req_qty?Math.round(qty/req_qty):0
}



// FUNCTION TO GET ITEM PROPERTY FROM ITEM MASTER
// async function getItemProperty(item, property) {
//     if (item && property) {
//         const properties = await frappe.db.get_list("Item Property Detail", {
//             filters: {
//                 parent: item,
//                 item_property: property
//             },
//             fields: ["item_property", "value"]
//         });

//         return properties[0]?.value;
//     }
// }

// for getting only the main body ratio
async function get_fg_to_rm_ratio_for_mb(frm){
    let bom = await frappe.db.get_doc("BOM",frm.doc.bom_no)
    let fg_qty = bom.quantity
    let required_qty_for_rm = 0
    bom.items?.forEach((row)=>{
        if(row.item_name?.toLowerCase().includes("main")){
            required_qty_for_rm+=row.qty
        }
    })
    let ratio = (parseFloat(fg_qty/required_qty_for_rm))
    return ratio
}

// MAIN BODY AND SEGREGATION
frappe.ui.form.on("Job Card Material Consumption",{
    // for wastage calculations
    wastage_qty:async function(frm,cdt,cdn){
        row = locals[cdt][cdn]
        if (row.wastage_qty){
        item = row.item ? row.item : ""
        if (item){
            let item_doc = await frappe.db.get_doc("Item",item)
            let conversion = 0
            item_doc.uoms.forEach((uom)=>{
                if(uom.uom === "Pound" || uom.uom === "lb"){
                    conversion = uom.conversion_factor
                }
            })
            frappe.model.set_value(cdt,cdn,"wastage_qty_in_item_uom",Math.round(row.wastage_qty/conversion || 1))
            frm.refresh_field("wastage_qty_in_item_uom")
        }
    }
    },

    material_consumed:async function(frm,cdt,cdn){
        row = locals[cdt][cdn]
            frappe.model.set_value(cdt,cdn,"process_loss",Math.round(row.qty-row.material_consumed))
            frm.refresh_field("wastage_qty_in_item_uom")
    },

    qty:async function(frm,cdt,cdn){
        row = locals[cdt][cdn]
        frappe.model.set_value(row.doctype,row.name,"process_loss",Math.round(row.qty - row.material_consumed))
    },

     // for check field of batch fully used? for main body only in ad*star entry
    async batch_fully_used(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        try {
            if (row.item_name?.toLowerCase().includes("body")) {
                if (row.batch_fully_used) {
                    frappe.model.set_value(cdt, cdn, "material_consumed", row.qty);
                    frm.refresh_field("material_consumed");
                } else if (row.manufactured_qty) {
                    // Get ratio from BOM
                    let ratio_fg = await frappe.call({
                        method: "tcb_manufacturing_customizations.doc_events.job_card.get_main_body_ratio",
                        args: { bom_no: frm.doc.bom_no }
                    });
                    
                    let mb_ratio = ratio_fg.message || 0;
                    if (mb_ratio) {
                        let required_mb = row.manufactured_qty / mb_ratio;
                        frappe.model.set_value(cdt, cdn, "material_consumed", Math.round(required_mb));
                        frm.refresh_field("material_consumed");
                    }
                }
            }
        } catch (e) {
            frappe.msgprint("Error: " + e);
        }
    },

    manufactured_qty: async function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.item_name?.toLowerCase().includes("body") && row.manufactured_qty && !row.batch_fully_used) {
            try {
                let ratio_fg = await frappe.call({
                    method: "tcb_manufacturing_customizations.doc_events.job_card.get_main_body_ratio",
                    args: { bom_no: frm.doc.bom_no }
                });
                
                let mb_ratio = ratio_fg.message || 0;
                if (mb_ratio) {
                    let required_mb = row.manufactured_qty / mb_ratio;
                    frappe.model.set_value(cdt, cdn, "material_consumed", Math.round(required_mb));
                    frm.refresh_field("material_consumed");
                }
            } catch (e) {
                frappe.msgprint("Error: " + e);
            }
        }
    }, 

    async roll_cut_lengths (frm,cdt,cdn){
        let row = locals[cdt][cdn]
        try{
            let required_qty = await get_wo_details(frm)
            // console.log("Required qty is",required_qty)

            // For SLitec Production---------------------------------------------
            let slitec_production = 0
                        
            if(row.roll_cut_lengths){
                let cutlengths = (row.roll_cut_lengths.trim().split(",").filter(n=>n))
                // console.log(cutlengths)
                let mat_consumed = cutlengths.reduce((acc,curr_val)=>{
                    return (Number(acc)+Number(curr_val))
                },0)

                if(mat_consumed>row.qty){
                    row.roll_cut_lengths = ""
                    frappe.throw(`The Consumption cannot be more than transferred qty at row ${row.idx}`)
                }

                // row.material_consumed = mat_consumed
                frappe.model.set_value(cdt,cdn,"material_consumed",mat_consumed)
                // console.log(mat_consumed)
           
                frm.refresh_field(row.material_consumed)


                for(let item of cutlengths){
                    slitec_production += parseFloat(item*required_qty)
                }
                
               
                frappe.model.set_value(row.doctype,row.name,"slitted_good_qty",slitec_production)

            }
        }
        catch (err){
            frappe.msgprint("Error Encountered",err)
        }
    },


    slitec_dialog_entry:function(frm,cdt,cdn){
        dialogbox(frm,cdt,cdn)
    }
})

// AD*STAR BAGS
frappe.ui.form.on("Job Card Material Consumption ADSTAR",{

    wastage_qty:async function(frm,cdt,cdn){
        row = locals[cdt][cdn]
        if (row.wastage_qty){
        item = row.item ? row.item : ""
        prod_item = frm.doc.production_item
        if (item){
            let item_doc = await frappe.db.get_doc("Item",item)
            let prod_doc = await frappe.db.get_doc("Item",prod_item)
            // console.log(prod_doc.custom_item_property_detail)
            let valve = prod_doc.custom_item_property_detail?.find((val)=>val.value?.toLowerCase().includes("valve"))
            // console.log(valve)
            let open_mouth = prod_doc.custom_item_property_detail?.find((val)=>val.value?.toLowerCase().includes("open mouth"))
            // console.log(open_mouth)
            // await getItemProperty(frm.doc.production_item,"Top Patch Width")
            // if(propertyexists){
            //     // console.log(propertyexists)
            // }
            let conversion = 0
            item_doc.uoms.forEach((uom)=>{
                if(uom.uom === "Pound" || uom.uom === "lb"){
                    conversion = uom.conversion_factor
                }
            })
            if(valve){
                frappe.model.set_value(row.doctype,row.name,"wastage_qty_in_item_uom",Math.round((row.wastage_qty/(conversion || 1))*0.75))
            }
            else if(open_mouth){
                frappe.model.set_value(row.doctype,row.name,"wastage_qty_in_item_uom",Math.round((row.wastage_qty/(conversion || 1))*0.90))
            }

            
            frm.refresh_field("wastage_qty_in_item_uom")
        }
    }
    },


    wastage_qty_in_item_uom:async function(frm,cdt,cdn){
        let row = locals[cdt][cdn]
        if(row.batch_fully_used==="No" && row.qty!=(row.wastage_qty_in_item_uom+row.material_consumed)){
            frappe.model.set_value(row.doctype,row.name,"qty",row.wastage_qty_in_item_uom+row.material_consumed)
        }
    },


    // NO PROCESS LOSS IN AD*STAR BAGS
    material_consumed:async function(frm,cdt,cdn){
        row = locals[cdt][cdn]
        if(row.item_name.toLowerCase().includes("patch") || row.item_name.toLowerCase().includes("valve")){
            frappe.model.set_value(cdt,cdn,"qty",Math.round(row.material_consumed))
        }
    },

    // qty:async function(frm,cdt,cdn){
    //     row = locals[cdt][cdn]
    //     frappe.model.set_value(row.doctype,row.name,"process_loss",Math.round(row.qty - row.material_consumed))
    // },

     // for check field of batch fully used? for main body only in ad*star entry
    async batch_fully_used(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        let original_qty = row.qty
        try {
            if (row.item_name?.toLowerCase().includes("body")) {
                if (row.batch_fully_used ==="Yes") {
                    frappe.model.set_value(row.doctype, row.name, "material_consumed", row.qty);
                    frm.refresh_field("material_consumed");
                } else if (row.manufactured_qty) {
                    // Get ratio from BOM
                    let ratio_fg = await frappe.call({
                        method: "tcb_manufacturing_customizations.doc_events.job_card.get_main_body_ratio",
                        args: { bom_no: frm.doc.bom_no }
                    });
                    
                    let mb_ratio = ratio_fg.message || 0;
                    if (mb_ratio) {
                        let required_mb = row.manufactured_qty / mb_ratio;
                        frappe.model.set_value(cdt, cdn, "material_consumed", Math.round(required_mb));
                        frm.refresh_field("material_consumed");
                    }
                    if (mb_ratio) {
                        const material_consumed = flt(row.material_consumed);
                        const wastage_qty = flt(row.wastage_qty_in_item_uom) || 0;
                        const original_qty = flt(row.qty);

                        const calculated_qty = material_consumed + wastage_qty;
                        const final_qty = Math.min(calculated_qty, original_qty);

                        frappe.model.set_value(
                            row.doctype,
                            row.name,
                            "qty",
                            final_qty
                        );
                    }

                }
            }
        } catch (e) {
            frappe.msgprint("Error: " + e);
        }
    },

    manufactured_qty: async function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.item_name?.toLowerCase().includes("body") && row.manufactured_qty && (row.batch_fully_used==="" || row.batch_fully_used==="No") ) {
            try {
                let ratio_fg = await frappe.call({
                    method: "tcb_manufacturing_customizations.doc_events.job_card.get_main_body_ratio",
                    args: { bom_no: frm.doc.bom_no }
                });
                
                let mb_ratio = ratio_fg.message || 0;
                if (mb_ratio) {
                    let required_mb = row.manufactured_qty / mb_ratio;
                    frappe.model.set_value(cdt, cdn, "material_consumed", Math.round(required_mb));
                    frm.refresh_field("material_consumed");
                }
            } catch (e) {
                frappe.msgprint("Error: " + e);
            }
        }
    }, 

})

// SLITTING
frappe.ui.form.on("Job Card Material Consumption Slitting",{
    // for wastage calculations
    wastage_qty:async function(frm,cdt,cdn){
        row = locals[cdt][cdn]
        if (row.wastage_qty){
        item = row.item ? row.item : ""
        if (item){
            let item_doc = await frappe.db.get_doc("Item",item)
            let conversion = 0
            item_doc.uoms.forEach((uom)=>{
                if(uom.uom === "Pound" || uom.uom === "lb"){
                    conversion = uom.conversion_factor
                }
            })
            frappe.model.set_value(cdt,cdn,"wastage_qty_in_item_uom",Math.round(row.wastage_qty/conversion || 1))
            frm.refresh_field("wastage_qty_in_item_uom")
        }
    }
    },

    material_consumed:async function(frm,cdt,cdn){
        row = locals[cdt][cdn]
            frappe.model.set_value(cdt,cdn,"process_loss",Math.round(row.qty-row.material_consumed))
            frm.refresh_field("wastage_qty_in_item_uom")
    },

    qty:async function(frm,cdt,cdn){
        row = locals[cdt][cdn]
        frappe.model.set_value(row.doctype,row.name,"process_loss",Math.round(row.qty - row.material_consumed))
    },


    async roll_cut_lengths (frm,cdt,cdn){
        let row = locals[cdt][cdn]
        try{
            let required_qty = await get_wo_details(frm)
            // console.log("Required qty is",required_qty)

            // For SLitec Production---------------------------------------------
            let slitec_production = 0
                        
            if(row.roll_cut_lengths){
                let cutlengths = (row.roll_cut_lengths.trim().split(",").filter(n=>n))
                // console.log(cutlengths)
                let mat_consumed = cutlengths.reduce((acc,curr_val)=>{
                    return (Number(acc)+Number(curr_val))
                },0)

                if(mat_consumed>row.qty){
                    row.roll_cut_lengths = ""
                    frappe.throw(`The Consumption cannot be more than transferred qty at row ${row.idx}`)
                }

                // row.material_consumed = mat_consumed
                frappe.model.set_value(cdt,cdn,"material_consumed",mat_consumed)
                // console.log(mat_consumed)
           
                frm.refresh_field(row.material_consumed)


                for(let item of cutlengths){
                    slitec_production += parseFloat(item*required_qty)
                }
                
               
                frappe.model.set_value(row.doctype,row.name,"slitted_good_qty",slitec_production)

            }
        }
        catch (err){
            frappe.msgprint("Error Encountered",err)
        }
    },


    slitec_dialog_entry:function(frm,cdt,cdn){
        dialogbox(frm,cdt,cdn)
    }
})

// NEW BTN FOR SLITEC 
// CUSTOM DIALOG BOX
function dialogbox(frm,cdt,cdn){
    let row = locals[cdt][cdn]
  let d = new frappe.ui.Dialog({
    title:"Cut Lengths Entry",
    size:"extra-large",
    fields:[
      {
        fieldtype:"HTML",
        fieldname:"custom_html"
      }
    ],
    primary_action_label:".",
    primary_action(){
        
      d.hide()
    }
  })

//   ASK FOR HOW MANY CUT LENGTHS
  d.fields_dict.custom_html.$wrapper.html(`
    <div style="display:flex; align-items:center; gap:10px;">
        <span>How many cut lengths are there for this roll?</span>
        <input id="cut_length_count" type="number" class="form-control" style="width:120px;">
        <button class="btn btn-primary btn-sm" id="confirm_cut_length">
            Confirm
        </button>
    </div>
    `)
  d.show()

  let wrapper = d.fields_dict.custom_html.$wrapper

  wrapper.find("#confirm_cut_length").on("click",function(){
    let value = wrapper.find("#cut_length_count").val()

// MAKE CONTAINERS BASED ON HOW MANY CUTLENGTHS
    let val_containers = ""
    for (let i = 0;i<value;i++){
        val_containers+=`&nbsp;&nbsp;<input type="text" class = "value_containers" placeholder = "Enter Cut-Length"></input>`
    }

// TAKE THE VALUES OF CUT LENGTHS AND PUSH INTO THE ROLL FIELD
    wrapper.html(`<div>${val_containers}<br/> <br/><button id = "finbtn">Set Cut-Lengths</button></div>`)
    wrapper.find("#finbtn").on("click",async function(){
        let inputValues = []
        wrapper.find(".value_containers").each(function(){
            let v = $(this).val()
            if (v){
                inputValues.push(v)
            }
        })


        let roll_values = inputValues.join(",")

        await frappe.model.set_value(
            row.doctype,row.name,"roll_cut_lengths",roll_values
        )
        
        d.hide()
    })
    
  })
}



// CALCULATE THE TOTAL WASTAGE QTY IN JOB CARD
frappe.ui.form.on("Job Card Scrap Item",{
    stock_qty:function(frm,cdt,cdn){
        let row = locals[cdt][cdn]
        row.custom_from_bom = 0
        let total_val = 0
        for(let r of frm.doc.scrap_items){
            total_val+=r.stock_qty
        }

        if(total_val) addtototal(frm,total_val)
    }
})

function addtototal(frm,value = 0){
    frm.set_value("custom_total_wastage",value)
}


// ===========================================================================
// BALES PLAN FEATURE
// ===========================================================================

// Show/hide Bales Plan section based on production_item group
function toggle_bales_plan_visibility(frm) {
    if (!frm.doc.production_item) {
        frm.set_df_property("custom_bales_plan_section", "hidden", 1);
        return;
    }

    frappe.call({
        method: "tcb_manufacturing_customizations.bales_utils.is_packaged_adstar_item",
        args: { item_code: frm.doc.production_item },
        callback: function(r) {
            console.log("Response : ", r)
            if (r.message) {
                frm.set_df_property("custom_bales_plan_section", "hidden", 0);
                // Calculate and set total segregated qty
                calculate_total_segregated_qty(frm);
            } else {
                frm.set_df_property("custom_bales_plan_section", "hidden", 1);
            }
        }
    });
}

// Calculate total qty from packaging materials with "segregated ad*star bags" group
function calculate_total_segregated_qty(frm) {
    if (!frm.doc.custom_packaging_materials || frm.doc.custom_packaging_materials.length === 0) {
        frm.set_value("custom_total_segregated_qty", 0);
        return;
    }

    frappe.call({
        method: "tcb_manufacturing_customizations.bales_utils.get_segregated_packaging_qty",
        args: {
            job_card: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value("custom_total_segregated_qty", r.message.total_qty || 0);
            }
        }
    });
}

// Calculate total bales qty planned
function calculate_total_bales_qty_planned(frm) {
    let total = 0;
    let unique_bales = new Set();

    if (frm.doc.custom_bales_plan) {
        for (let row of frm.doc.custom_bales_plan) {
            if (row.bale_number && !unique_bales.has(row.bale_number)) {
                unique_bales.add(row.bale_number);
                total += flt(row.bale_qty);
            }
        }
    }

    frm.set_value("custom_total_bales_qty_planned", total);
}

// Generate Bales Plan button handler
function generate_bales_plan(frm) {
    // Validate packaging materials exist
    if (!frm.doc.custom_packaging_materials || frm.doc.custom_packaging_materials.length === 0) {
        frappe.msgprint(__("No packaging materials found. Please transfer materials first."));
        return;
    }

    // Get bale qty from production item
    frappe.db.get_value("Item", frm.doc.production_item, "custom_bale_qty", (r) => {
        if (!r || !r.custom_bale_qty || flt(r.custom_bale_qty) <= 0) {
            frappe.msgprint(__("Production item does not have a valid Bale Qty defined."));
            return;
        }

        let bale_qty = flt(r.custom_bale_qty);
        let total_segregated_qty = flt(frm.doc.custom_total_segregated_qty);

        if (total_segregated_qty <= 0) {
            frappe.msgprint(__("No segregated packaging materials available."));
            return;
        }

        // Show dialog to let user customize number of bales
        frappe.prompt([
            {
                fieldname: "bale_qty",
                fieldtype: "Float",
                label: "Qty per Bale",
                default: bale_qty,
                reqd: 1
            },
            {
                fieldname: "info",
                fieldtype: "HTML",
                options: `<div class="alert alert-info">
                    <b>Total Segregated Qty Available:</b> ${format_number(total_segregated_qty)}<br>
                    <b>Default Bale Qty from Item:</b> ${format_number(bale_qty)}<br>
                    <b>Suggested Bales:</b> ${Math.floor(total_segregated_qty / bale_qty)} full + ${total_segregated_qty % bale_qty > 0 ? '1 partial' : '0 partial'}
                </div>`
            }
        ], (values) => {
            let qty_per_bale = flt(values.bale_qty);
            if (qty_per_bale <= 0) {
                frappe.msgprint(__("Invalid bale qty."));
                return;
            }

            // Call backend to generate plan with FIFO batch split
            frappe.call({
                method: "tcb_manufacturing_customizations.bales_utils.generate_bales_plan",
                args: {
                    job_card: frm.doc.name,
                    bale_qty: qty_per_bale
                },
                freeze: true,
                freeze_message: __("Generating Bales Plan..."),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frm.reload_doc();
                        frm.save()
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: "green"
                        });
                    } else {
                        frappe.msgprint(r.message?.error || __("Failed to generate bales plan."));
                    }
                }
            });
        }, __("Generate Bales Plan"), __("Generate"));
    });
}

// Button click handler for Generate Bales Plan
frappe.ui.form.on("Job Card", {
    custom_generate_bales_plan: function(frm) {
        generate_bales_plan(frm);
    },

    custom_packaging_materials_on_form_rendered: function(frm) {
        // Recalculate segregated qty when packaging materials change
        calculate_total_segregated_qty(frm);
    }
});

// Job Card Bales Plan child table handlers
frappe.ui.form.on("Job Card Bales Plan", {
    custom_bales_plan_remove: function(frm) {
        calculate_total_bales_qty_planned(frm);
    },

    bale_qty: function(frm, cdt, cdn) {
        calculate_total_bales_qty_planned(frm);
    },

    bale_number: function(frm, cdt, cdn) {
        calculate_total_bales_qty_planned(frm);
    }
});


// JOB CARD PACKAGING MATERIAL - Batch selection for segregated items
frappe.ui.form.on("Job Card Packaging Material", {
    // Set batch filter to show only available batches (not used in Bales)
    batch_no: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.batch_no) {
            // Fetch sub_batch when batch is selected
            frappe.db.get_value("Batch", row.batch_no, "custom_sub_batch", (r) => {
                if (r) {
                    frappe.model.set_value(cdt, cdn, "sub_batch", r.custom_sub_batch || "");
                }
            });
        }
    },

    // Setup query filter for batch_no field
    form_render: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Check if item is segregated - only then allow batch editing
        if (row.item_code) {
            frappe.call({
                method: "tcb_manufacturing_customizations.bales_utils.is_segregated_item",
                args: { item_code: row.item_code },
                callback: function(r) {
                    if (r.message) {
                        // Item is segregated - enable batch selection
                        frm.fields_dict.custom_packaging_materials.grid.grid_rows_by_docname[cdn].toggle_editable("batch_no", true);

                        // Set query filter for batch_no
                        frm.fields_dict.custom_packaging_materials.grid.get_field("batch_no").get_query = function(doc, cdt, cdn) {
                            let child_row = locals[cdt][cdn];
                            return {
                                query: "tcb_manufacturing_customizations.bales_utils.get_batch_query_for_packaging",
                                filters: {
                                    item_code: child_row.item_code,
                                    warehouse: child_row.warehouse
                                }
                            };
                        };
                    } else {
                        // Item is not segregated - disable batch editing
                        frm.fields_dict.custom_packaging_materials.grid.grid_rows_by_docname[cdn].toggle_editable("batch_no", false);
                    }
                }
            });
        }
    }
});



