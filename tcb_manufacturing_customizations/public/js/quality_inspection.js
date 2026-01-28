frappe.ui.form.on("Quality Inspection",{
    onload:function(frm){
        if(frm.is_new && !frm.doc.custom_on_hold){
            // set it hidden so that no one may accidentally set it
            frm.set_df_property("custom_on_hold","hidden",1)
        }
    },
    after_save:function(frm){
        if(frm.doc.status=="Accepted" && frm.doc.manual_inspection){
            frappe.call({
                // we had made a python method and this is the link to that method
                method:"tcb_manufacturing_customizations.api.api.get_qc_status",
                args:{
                    qc_doc:frm.doc.name
                },
                callback:(r)=>{
                    // we get this response from the python method
                    if (r.message =="Confirmed"){
                        if(frm.doc.custom_on_hold){
                            // if the checkbox is true then we set it non hidden
                            frm.set_df_property("custom_on_hold","hidden",0)
                            frm.refresh_field("custom_on_hold")
                        }
                    }
                    else if (r.message =="Nothing"){
                        if(frm.doc.custom_on_hold){
                            frm.set_df_property("custom_on_hold","hidden",1)
                            frm.refresh_field("custom_on_hold")
                        }
                    }
                }
            })
        }
    },
    before_save:function(frm){
        if (frm.doc.custom_on_hold){
            frm.set_df_property("remarks","reqd",1)
            frm.refresh_field("remarks")
        }
        else if (!frm.doc.custom_on_hold){
            frm.set_df_property("remarks","reqd",0)
            frm.refresh_field("remarks")
        }
    },

    // Hide Submit button when the on hold button is checked
    refresh: function(frm) {
        if(frm.doc.docstatus==0){
            if(!frm.doc.custom_on_hold1){
                // To-do -> if accepted with deviation then auto click remove from hold
                frm.add_custom_button("Put on Hold",()=>{
                    frm.set_value("custom_on_hold1",1)
                    frm.remove_custom_button("Put on Hold")
                })
            }
            else if(frm.doc.custom_on_hold1){
                frm.add_custom_button("Remove from Hold",()=>{
                    frm.set_value("custom_on_hold1",0)
                    frm.remove_custom_button("Remove from Hold")
                })
            }
        }
        

        if (frm.doc.custom_on_hold1) {
            // hides the submit button(primary action)
            frm.page.clear_primary_action();
            // sets page indicator to on hold
            frm.page.set_indicator("On Hold", "orange");
        } else {
            // sets the primary action(submit) property from hidden to shown
            $('.primary-action').prop('hidden', false);
        }
    },

    custom_on_hold1: function(frm) {
        if (frm.doc.custom_on_hold1) {
            frm.page.clear_primary_action();
            frm.page.set_indicator("On Hold", "orange");
        } else {
            $('.primary-action').prop('hidden', false);
        }
        frm.save();
    }
})