// frappe.ui.form.on("Bales", {
//     refresh: function(frm) {
//         if (!frm.doc.bale_qty) {
//             let sum = 0;
//             frm.doc.batches_used.forEach((b) => {
//                 sum += b.qty_taken;
//             });
//             frappe.db.set_value("Bales", frm.doc.name, "bale_qty", sum);
//         }

//         if (!frm.doc.posting_date) {
//             frappe.db.set_value("Bales", frm.doc.name, "posting_date", frappe.datetime.get_today());
//         }
//         if (frm.doc.workflow_state) {
//             let color = {
//                 'Draft': 'orange',
//                 'Available': 'green',
//                 'Dispatched': 'blue'
//             }[frm.doc.workflow_state] || 'grey';
            
//             frm.dashboard.add_indicator(__('Status: {0}', [frm.doc.workflow_state]), color);
//         }
        
//         // Show button to consume materials for manufactured bales
//         if (frm.doc.bales_source === 'Manufactured' 
//             && frm.doc.workflow_state === 'Draft' 
//             && frm.doc.docstatus === 0) {
            
//             // Add prominent button with styling
//             frm.add_custom_button(__('Consume Baling Materials'), function() {
//                 frm.trigger('consume_baling_materials');
//             }).addClass('btn-primary');  // Make it stand out
            
//             // Show warning indicator if no consumption entry
//             if (!frm.doc.custom_material_consumption_entry) {
//                 frm.dashboard.add_indicator(
//                     __('Material Consumption Required'), 
//                     'orange'
//                 );
//             }
//         }

//         if(frm.doc.custom_material_consumption_entry){
//             frm.hide_custom_button("Consume Baling Materials")
//         }
        
//         // Show linked Stock Entry if exists
//         if (frm.doc.custom_material_consumption_entry) {
//             frm.add_custom_button(__('View Material Consumption'), function() {
//                 frappe.set_route('Form', 'Stock Entry', frm.doc.custom_material_consumption_entry);
//             });
            
//             frm.dashboard.add_indicator(
//                 __('Materials Consumed'), 
//                 'green'
//             );
//         }
        
//         // IMPORTANT: Override workflow actions to check material consumption
//         if (frm.doc.bales_source === 'Manufactured' && frm.doc.workflow_state === 'Draft') {
//             override_workflow_buttons(frm);
//         }
//     },
    
//     // This triggers when workflow state changes
//     workflow_state: function(frm) {
//         console.log("Workflow state changed to:", frm.doc.workflow_state);
//         check_material_consumption_requirement(frm);
//     },
    
//     // Also check after save (workflow changes trigger save)
//     after_save: function(frm) {
//         console.log("After save - workflow state:", frm.doc.workflow_state);
//         check_material_consumption_requirement(frm);
//     },
    
//     // Also check on validate (before save)
//     validate: function(frm) {
//         console.log("Validate - workflow state:", frm.doc.workflow_state);
//         // Don't block save, just warn
//         if (frm.doc.workflow_state === 'Available' 
//             && frm.doc.bales_source === 'Manufactured'
//             && !frm.doc.custom_material_consumption_entry) {
//             console.warn("Moving to Available without material consumption");
//         }
//     },
    
//     consume_baling_materials: function(frm) {
//         console.log("Consuming baling materials for:", frm.doc.name);
        
//         // Get required materials for this bale
//         frappe.call({
//             method: "tcb_manufacturing_customizations.doc_events.production_plan.get_bale_material_consumption_entry",
//             args: {
//                 bale_doc_name: frm.doc.name
//             },
//             callback: function(r) {
//                 console.log("Server response:", r);
                
//                 if (r.message && r.message.length > 0) {
//                     console.log("Materials required:", r.message);
//                     show_material_consumption_dialog(frm, r.message);
//                 } else {
//                     frappe.msgprint(__('No BOM found for baling materials or no materials required'));
//                 }
//             },
//             error: function(err) {
//                 console.error("Error fetching materials:", err);
//                 frappe.msgprint(__('Error fetching material requirements. Check console for details.'));
//             }
//         });
//     }
// });

// // Separate function to check if material consumption is needed
// function check_material_consumption_requirement(frm) {
//     console.log("Checking material consumption requirement...");
//     console.log("Current state:", frm.doc.workflow_state);
//     console.log("Bales source:", frm.doc.bales_source);
//     console.log("Material consumption entry:", frm.doc.custom_material_consumption_entry);
    
//     // When moving to Available, check if materials consumed (for Manufactured)
//     if (frm.doc.workflow_state === 'Available' 
//         && frm.doc.bales_source === 'Manufactured'
//         && !frm.doc.custom_material_consumption_entry) {
        
//         console.log("Prompting for material consumption");
        
//         frappe.confirm(
//             __('This bale requires material consumption. Do you want to consume materials now?'),
//             function() {
//                 // Yes - consume materials
//                 frm.trigger('consume_baling_materials');
//             },
//             function() {
//                 // No - just show warning
//                 frappe.msgprint({
//                     title: __('Warning'),
//                     message: __('Please consume materials before completing this bale. You can use the "Consume Baling Materials" button.'),
//                     indicator: 'orange'
//                 });
//             }
//         );
//     }
// }

// // Define as standalone function for the dialog
// function show_material_consumption_dialog(frm, required_items) {
//     console.log("Showing material consumption dialog");
//     console.log("Required items:", required_items);
    
//     let fields = [];
    
//     // Add fields for each required item
//     required_items.forEach((item, index) => {
//         fields.push({
//             fieldtype: 'Section Break',
//             label: `${item.item_name} (${item.item_code})`
//         });
        
//         fields.push({
//             fieldtype: 'Data',
//             fieldname: `item_code_${index}`,
//             label: 'Item Code',
//             read_only: 1,
//             default: item.item_code
//         });
        
//         fields.push({
//             fieldtype: 'Column Break'
//         });
        
//         fields.push({
//             fieldtype: 'Float',
//             fieldname: `qty_${index}`,
//             label: 'Required Qty',
//             read_only: 1,
//             default: item.required_qty,
//             precision: 3
//         });
        
//         fields.push({
//             fieldtype: 'Column Break'
//         });
        
//         fields.push({
//             fieldtype: 'Link',
//             fieldname: `warehouse_${index}`,
//             label: 'Warehouse',
//             options: 'Warehouse',
//             reqd: 1,
//             default: frm.doc.warehouse || frappe.defaults.get_user_default('Warehouse'),
//             onchange: function() {
//                 // Refresh batch filter when warehouse changes
//                 let warehouse = this.get_value();
//                 if (warehouse) {
//                     console.log(`Warehouse selected for item ${index}:`, warehouse);
//                 }
//             }
//         });
        
//         // fields.push({
//         //     fieldtype: 'Column Break'
//         // });
        
//         // fields.push({
//         //     fieldtype: 'Link',
//         //     fieldname: `batch_${index}`,
//         //     label: 'Batch',
//         //     options: 'Batch',
//         //     get_query: function() {
//         //         let dialog = this;
//         //         let warehouse_field = `warehouse_${index}`;
//         //         let warehouse = dialog.fields_dict[warehouse_field]?.get_value();
                
//         //         let filters = {
//         //             'item': item.item_code,
//         //             'batch_qty': ['>', 0]
//         //         };
                
//         //         if (warehouse) {
//         //             filters['warehouse'] = warehouse;
//         //         }
                
//         //         return { filters: filters };
//         //     }
//         // });
//     });
    
//     let d = new frappe.ui.Dialog({
//         title: __('Consume Baling Materials'),
//         fields: fields,
//         size: 'large',
//         primary_action_label: __('Create Stock Entry'),
//         primary_action: function() {
//             let values = d.get_values();
//             console.log("Dialog values:", values);
            
//             // Validate that all required fields are filled
//             let validation_failed = false;
//             required_items.forEach((item, index) => {
//                 if (!values[`warehouse_${index}`]) {
//                     frappe.msgprint(__('Please select warehouse for {0}', [item.item_name]));
//                     validation_failed = true;
//                 }
//             });
            
//             if (validation_failed) {
//                 return;
//             }
            
//             // Prepare items array
//             let items = [];
//             required_items.forEach((item, index) => {
//                 items.push({
//                     item_code: values[`item_code_${index}`],
//                     qty: values[`qty_${index}`],
//                     warehouse: values[`warehouse_${index}`],
//                     // batch_no: values[`batch_${index}`] || null
//                 });
//             });
            
//             console.log("Creating stock entry with items:", items);
            
//             // Show loading indicator
//             frappe.show_alert({
//                 message: __('Creating Stock Entry...'),
//                 indicator: 'blue'
//             });
            
//             // Create Stock Entry
//             frappe.call({
//                 method: "tcb_manufacturing_customizations.doc_events.production_plan.create_consumption_stock_entry_for_bale",
//                 args: {
//                     bale_name: frm.doc.name,
//                     items_json: JSON.stringify(items)
//                 },
//                 freeze: true,
//                 freeze_message: __('Creating Stock Entry...'),
//                 callback: function(r) {
//                     if (r.message) {
//                         frappe.show_alert({
//                             message: __('Stock Entry {0} created successfully', [r.message]),
//                             indicator: 'green'
//                         });
                        
//                         // Update bale with reference
//                         frappe.model.set_value(frm.doctype, frm.docname, 
//                                              'custom_material_consumption_entry', r.message);
                        
//                         d.hide();
//                         frm.save('Update').then(() => {
//                             frm.reload_doc();
                            
//                             // Ask if user wants to view/submit the Stock Entry
//                             frappe.confirm(
//                                 __('Material consumption entry created. Do you want to open it now?'),
//                                 function() {
//                                     frappe.set_route('Form', 'Stock Entry', r.message);
//                                 }
//                             );
//                         });
//                     }
//                 },
//                 error: function(err) {
//                     console.error("Error creating stock entry:", err);
//                     frappe.msgprint({
//                         title: __('Error'),
//                         message: __('Error creating stock entry. Check console for details.'),
//                         indicator: 'red'
//                     });
//                 }
//             });
//         }
//     });
    
//     d.show();
// }

// // Override workflow action buttons to check material consumption first
// function override_workflow_buttons(frm) {
//     // Wait for workflow buttons to load
//     setTimeout(() => {
//         // Find all workflow action buttons
//         $('.btn-workflow-action').each(function() {
//             let $btn = $(this);
//             let action = $btn.attr('data-action');
            
//             // If the action leads to "Available" state
//             if (action && (action.includes('Available') || action.includes('Approve'))) {
//                 // Store the original click handler
//                 let original_handler = $._data($btn[0], 'events')?.click?.[0]?.handler;
                
//                 if (original_handler) {
//                     // Remove the original handler
//                     $btn.off('click');
                    
//                     // Add our custom handler
//                     $btn.on('click', function(e) {
//                         e.preventDefault();
//                         e.stopPropagation();
                        
//                         // Check if material consumption is done
//                         if (!frm.doc.custom_material_consumption_entry) {
//                             frappe.confirm(
//                                 __('This bale requires material consumption before moving to Available. Do you want to consume materials now?'),
//                                 function() {
//                                     // Yes - consume materials first
//                                     frm.trigger('consume_baling_materials');
//                                 },
//                                 function() {
//                                     // No - ask if they want to proceed anyway
//                                     frappe.confirm(
//                                         __('Are you sure you want to proceed without consuming materials? This is not recommended.'),
//                                         function() {
//                                             // Proceed with original workflow action
//                                             original_handler.call($btn[0], e);
//                                         }
//                                     );
//                                 }
//                             );
//                         } else {
//                             // Material consumption done, proceed with workflow
//                             original_handler.call($btn[0], e);
//                         }
//                     });
//                 }
//             }
//         });
//     }, 500);  // Wait for workflow buttons to render
// }