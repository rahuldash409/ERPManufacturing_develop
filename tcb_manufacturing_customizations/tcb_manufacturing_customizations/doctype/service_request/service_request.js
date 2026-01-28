// Copyright (c) 2025, TCB Infotech Private Limited and contributors
// For license information, please see license.txt

async function create_po_button_visibility(frm) {
    if (frm.doc.docstatus !== 1 || frm.doc.workflow_state !== "Approved") return;

    const r = await frappe.db.get_list("Purchase Order", {
        filters: {
            custom_po_reference: frm.doc.name,
            docstatus: ["!=", 2]
        },
        fields: ["name", "docstatus"],
        limit: 1
    });

    if (r.length && r[0].docstatus === 1) {
        return;
    }

    frm.add_custom_button(__('Create Purchase Order'), async () => {
        await create_po_from_service_request(frm);
    },);
}

frappe.ui.form.on("Service Request", {
    refresh: async function(frm) {
        await create_po_button_visibility(frm);
        // Show custom Reject button on Pending For Level 2 workflow state
        if (frm.doc.workflow_state === "Pending For Level 2") {
            // console.log("Adding custom Reject button workslofw state:", frm.doc.workflow_state);
            frm.add_custom_button(__('Reject Service Request'), () => {
                show_rejection_dialog(frm);
            },).addClass('btn btn-primary btn-sm');
        }
    },
    
    onload: function(frm) {
        frm.doc.__onload = frm.doc.__onload || {};        
        if (!frm.doc.__original_workflow_state) {
            frm.doc.__original_workflow_state = frm.doc.workflow_state;
        }
    },

    before_workflow_action: function(frm) {
        let action = frm.selected_workflow_action;
        
        if (action === "Approve And Submit") {
            setTimeout(() => {
                update_move_histories_on_approval(frm.doc.name);
            }, 500);
        }
        
        // if (action && action.toLowerCase().includes("reject")) {
        
        // }
    }
});

function update_move_histories_on_approval(sr_name) {
    frappe.call({
        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.service_request.service_request.update_move_histories_on_approval",
        args: {
            sr_name: sr_name
        },
        callback: function(r) {
            if (r.message) {
                frappe.show_alert({
                    message: __('Move Histories updated: {0} records', [r.message.count]),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}

//  2: New function - Show rejection dialog
function show_rejection_dialog(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Reject Service Request'),
        size: 'large',
        fields: [
            {
                fieldname: 'warning',
                fieldtype: 'HTML',
                options: `
                    <div style="padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107; margin-bottom: 15px;">
                        <b><i class="fa fa-exclamation-triangle"></i> Warning:</b><br>
                        You are about to reject this Service Request.<br>
                        All spare items will be returned from <b>Damaged Warehouse</b>.
                    </div>
                `
            },
            {
                fieldname: 'return_status',
                fieldtype: 'Select',
                label: __('Return Status for Spares'),
                options: [
                    '',
                    'Available',
                    'In Use'
                ],
                reqd: 1,
                description: __('Available: Return to Storage Warehouse | In Use: Return to Workstation Warehouse')
            },
            {
                fieldname: 'rejection_reason',
                fieldtype: 'Small Text',
                label: __('Rejection Reason'),
                reqd: 1
            },
            {
                fieldname: 'info',
                fieldtype: 'HTML',
                options: `
                    <div style="padding: 10px; background: #e3f2fd; border-left: 4px solid #2196F3; margin-top: 15px;">
                        <b><i class="fa fa-info-circle"></i> What happens:</b><br>
                        • <b>Available:</b> Items will be moved to Storage Warehouse (ready for future use)<br>
                        • <b>In Use:</b> Items will be moved back to their Workstation's Warehouse (active use)<br>
                        • A Stock Entry will be created automatically<br>
                        • Service Request will be rejected
                    </div>
                `
            }
        ],
        primary_action_label: __('Reject & Return Spares'),
        primary_action: function(values) {
            if (!values.return_status) {
                frappe.msgprint(__('Please select a return status'));
                return;
            }
            
            if (!values.rejection_reason) {
                frappe.msgprint(__('Please provide a rejection reason'));
                return;
            }
            
            dialog.hide();
            
            frappe.confirm(
                __('Confirm Rejection?<br><br>This will:<br>• Return all spares to {0} status<br>• Create a stock entry<br>• Reject the Service Request', 
                    [values.return_status]),
                function() {
                    frappe.dom.freeze(__('Processing rejection...'));
                    
                    frappe.call({
                        method: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.service_request.service_request.reject_service_request_with_spares_return',
                        args: {
                            sr_name: frm.doc.name,
                            return_status: values.return_status,
                            rejection_reason: values.rejection_reason
                        },
                        callback: function(r) {
                            frappe.dom.unfreeze();
                            
                            if (r.message && r.message.success) {
                                frappe.msgprint({
                                    title: __('Service Request Rejected'),
                                    message: __('Stock Entry <b>{0}</b> created with {1} items.<br>Service Request has been rejected.', 
                                        [r.message.stock_entry_name, r.message.items_count]),
                                    indicator: 'orange'
                                });
                                
                                // Reload and apply rejection workflow
                                frm.reload_doc();
                                
                                // Navigate to stock entry after a delay
                                setTimeout(() => {
                                    frappe.set_route('Form', 'Stock Entry', r.message.stock_entry_name);
                                }, 2000);
                            }
                        },
                        error: function(err) {
                            frappe.dom.unfreeze();
                            frappe.msgprint({
                                title: __('Error'),
                                message: __('Failed to process rejection. Please try again or contact support.'),
                                indicator: 'red'
                            });
                        }
                    });
                }
            );
        }
    });
    
    dialog.show();
}

// Keep existing rejection function for backward compatibility
function update_move_histories_on_rejection(sr_name) {
    frappe.call({
        method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.service_request.service_request.update_move_histories_on_rejection",
        args: {
            sr_name: sr_name
        },
        callback: function(r) {
            if (r.message) {
                frappe.show_alert({
                    message: __('Move Histories marked as rejected: {0} records', [r.message.count]),
                    indicator: 'orange'
                }, 5);
            }
        }
    });
}

async function create_po_from_service_request(frm) {
    const existing = await frappe.db.get_list("Purchase Order", {
        filters: {
            custom_po_reference: frm.doc.name,
            docstatus: ["!=", 2]
        },
        fields: ["name", "docstatus"],
        limit: 1
    });

    if (existing.length) {
        if (existing[0].docstatus === 0) {
            frappe.throw(`
                A Draft Purchase Order <b>${existing[0].name}</b> already exists.<br><br>
                Please complete or submit that PO instead of creating a new one.
            `);
        } else {
            frappe.throw(`
                A Submitted Purchase Order <b>${existing[0].name}</b> already exists.<br><br>
                Only one PO is allowed per Service Request.
                Cancel it first if you want to create a new one.
            `);
        }
        return;
    }

    frappe.confirm(
        __("Create Purchase Order from this Service Request?"),
        async () => {
            frappe.dom.freeze("Creating Purchase Order...");
            try {
                const r = await frappe.call({
                    method: "tcb_manufacturing_customizations.tcb_manufacturing_customizations.doctype.service_request.service_request.create_po_from_sr",
                    args: { sr_name: frm.doc.name }
                });

                frappe.msgprint({
                    title: "Purchase Order Created",
                    message: `PO <b>${r.message.po_name}</b> created successfully`,
                    indicator: "green"
                });

                frm.reload_doc();
                frappe.set_route("Form", "Purchase Order", r.message.po_name);
            } finally {
                frappe.dom.unfreeze();
            }
        }
    );
}
