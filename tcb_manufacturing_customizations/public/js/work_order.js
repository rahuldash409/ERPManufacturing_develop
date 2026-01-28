frappe.ui.form.on("Work Order", {
  after_save:function(frm){
    if(frm.doc.operations?.length>0 && !frm.doc.custom_after_insert_done){
      frm.doc.operations.forEach(async (row)=>{
        if(!row.workstation){
          let wkn = await frappe.db.get_value("Operation",row.operation,"workstation")
          if(wkn){
            await frappe.model.set_value(row.doctype,row.name,"workstation",wkn.message.workstation)  
            frm.doc.custom_after_insert_done = 1
            frm.save()
          }
        }
      })
    }
  },
  
  refresh: (frm) => {

    frm.remove_custom_button("Create Pick List")

    // frm.doc.operations.forEach((opn,cdt,cdn)=>{
    //   let row = locals[cdt][cdn]
    //   if(!opn.workstation){
    //     val = frappe.db.get_value("Operation",opn.operation,"workstation")
    //     frappe.model.set_value(row.doctype,row.name,"workstation",val)
    //   }
    // })

    
    if (frm.doc.docstatus == 1) {
      frm.remove_custom_button(__("Finish"));
      var finish_btn = frm.add_custom_button(__("Finish"), function () {
        erpnext.work_order.make_se_advance(frm, "Manufacture");
      });
      finish_btn.addClass("btn-primary");
    }
  },
  production_item: function(frm) {
        setTimeout(() => {
            if (frm.doc.bom_no) {
                frm.trigger('auto_set_warehouses_from_bom');
            }
        }, 500);
    },
    
    bom_no: function(frm) {
        if (frm.doc.bom_no) {
            frm.trigger('auto_set_warehouses_from_bom');
        }
    },
    
    auto_set_warehouses_from_bom: async function(frm) {
        if (!frm.doc.bom_no) {
            return;
        }
        
        
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "BOM",
                name: frm.doc.bom_no
            },
            callback: function(r) {
                if (r.message) {
                    let bom = r.message;
                    
                    // Set source warehouse
                    if (!frm.doc.source_warehouse && bom.custom_raw_material_warehouse) {
                        frm.set_value("source_warehouse", bom.custom_raw_material_warehouse);
                    }
                    
                    // Set WIP warehouse
                    if (!frm.doc.wip_warehouse && bom.custom_work_in_progress_warehouse) {
                        frm.set_value("wip_warehouse", bom.custom_work_in_progress_warehouse);
                    }
                    
                    // Set FG warehouse
                    if (!frm.doc.fg_warehouse && bom.custom_finished_goods_warehouse) {
                        frm.set_value("fg_warehouse", bom.custom_finished_goods_warehouse);
                    }
                    
                    // Set scrap warehouse
                    if (!frm.doc.scrap_warehouse && bom.custom_scrap_warehouse) {
                        frm.set_value("scrap_warehouse", bom.custom_scrap_warehouse);
                    }
                }
            }
        });
    },
  
    update_source_warehouse: (frm)=>{
      try{
        let source_warehouse = frm.doc.source_warehouse;
        let required_items = getAttr(frm.doc, "required_items", [])
        required_items.forEach(item=>{
          if(item.source_warehouse != source_warehouse){
            frappe.model.set_value(item.doctype, item.name, "source_warehouse", source_warehouse)
          }
        })
      }
      catch(err){
        
      }
    },
    source_warehouse: (frm)=>{
      frm.trigger("update_source_warehouse")
    }
});


erpnext.work_order.make_se_advance = (frm, purpose) => {
  frappe.call({
    method: "frappe.client.get_list",
    args: {
      doctype: "Job Card",
      filters: {
        work_order: frm.doc.name,
        custom_stock_entry_reference: "",
        docstatus: 1,
      },
      fields: ["name as job_card", "total_completed_qty as qty"],
    },
    callback: (r) => {
      if (r.message) {
        get_job_cards(r.message);
      }
    },
  });
  function get_job_cards(data) {
    const job_card_table = [
      {
        fieldname: "job_card",
        fieldtype: "Link",
        label: "Job Card",
        options: "Job Card",
        read_only: 1,
        in_list_view: 1,
        columns: 2,
      },
      {
        fieldname: "qty",
        fieldtype: "Float",
        label: "Completed Qty",
        read_only: 1,
        in_list_view: 1,
        columns: 2,
      },
    ];
    let d = new frappe.ui.Dialog({
      title: "Get Job Card Qty",
      fields: [
        {
          fieldname: "job_cards",
          fieldtype: "Table",
          label: "Job Cards (Select to finalize for manufacture)",
          cannot_add_rows: true,
          cannot_delete_rows: true,
          in_place_edit: false,
          read_only: false,
          reqd: 0,
          fields: job_card_table,
          data: data,
        },
      ],
      size: "large",
      primary_action_label: "Finish",
      secondary_action_label: "Cancel",
      static: true,
      primary_action: (values) => {
        let selected_items = values.job_cards.filter(
          (job_card) => job_card.__checked
        );
        if (selected_items.length > 0) {
          let total_qty = 0;
          selected_items.forEach((job_card) => {
            total_qty += job_card.qty;
          });
          let jc_list = [];
          selected_items.forEach((item) => {
            if (!jc_list.includes(item.job_card)) {
              jc_list.push(item.job_card);
            }
          });
          if (total_qty > 0) {
            frappe.msgprint(`Qty to manufacture is ${total_qty}`);
            frappe
              .xcall(
                "erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry",
                {
                  work_order_id: frm.doc.name,
                  purpose: purpose,
                  qty: total_qty,
                  mat_entry_type: "Manufacture",
                  jc_list: jc_list.join(","),
                }
              )
              .then((se) => {
                frappe.model.sync(se);
                frappe.set_route("Form", se.doctype, se.name);
              });
          }
        }
        d.hide();
      },
      secondary_action: (values) => {
        d.hide();
      },
    });
    d.show();
  }
};


// Utils Start
function cleanValue(variable, default_value) {
	return variable
		? variable
		: default_value || isNaN(variable)
			? default_value
			: variable;
}

function getAttr(obj, key, default_value = null) {
	key = key.trim();
	try {
		return cleanValue(obj[key], default_value);
	} catch (err) {
		return default_value;
	}
}

function isObjectsEquel(obj1, obj2) {
	return JSON.stringify(obj1) === JSON.stringify(obj2)
}
// Utils End