frappe.ui.form.on("Stock Entry", {
  // frm setup for the first time
  // setup:function(frm){
  // },


  onload: function (frm) {
    frm.set_df_property("custom_quick_entry", "allow_bulk_edit", 1);
    frm.toggle_display("custom_quick_entry", frm.doc.docstatus == 0);
    frm.toggle_display("custom_submit", frm.doc.docstatus == 0);
    frm.toggle_display("custom_sync_sub_batch_qty", frm.doc.docstatus == 0);
    toggle_properties_workstation_consumables_spares(frm);

    frappe.ui.form.on_change("Stock Entry Detail", "item_code", (frm, cdt, cdn)=>{
      frm.trigger("refresh_serial_batch_popup")
    })

  },

  
  stock_entry_type:function(frm){
    if(frm.doc.stock_entry_type==="Manufacture" || frm.doc.stock_entry_type==="Material Transfer for Manufacture"){
      frm.set_df_property("custom_section_break_0cpny","collapsed",0)
    }
  },    

  onload_post_render: function (frm) {

    // transferring materials for the job card for the production,, we need to autosave and auto sync batches
    // if(frm.is_new() && frm.doc.custom_quick_entry.length > 0 && frm.get_field("job_card").value!=undefined){

    // SET ITEMS IN QUICK ENTRY TABLE
    if (
      frm.doc.items &&
      frm.doc.docstatus == 0 &&
      frm.doc.stock_entry_type == "Material Transfer for Manufacture"
    ) {


      existing_items = frm.doc.custom_quick_entry?.map((e) => e.item) || [];

      if (frm.doc.custom_quick_entry != 1) {
        frm.doc.items.forEach((item) => {
          frappe.db.get_doc("Item", item.item_code).then((doc) => {
            if (
              doc.has_batch_no &&
              !existing_items.includes(doc.name) &&
              !item.is_finished_item &&
              !item.is_scrap_item
            ) {
                // frm.clear_table("custom_quick_entry")

              frm.add_child("custom_quick_entry", {
                item: item.item_code,
                source_warehouse: item.t_warehouse || "",
              });
              frm.add_child("custom_quick_entry", {
                item: item.item_code,
                source_warehouse: item.s_warehouse || "",
              });
              frm.refresh_field("custom_quick_entry");
            }
          });
        });


        // For AUTO TRIGGERING THE SYNC SUB BATCH BUTTON
        if(frm.is_dirty() && frm.is_new() && frm.get_field("job_card").value && frm.get_field("stock_entry_type").value==="Material Transfer for Manufacture"){
          frm.save()
          .then(()=>{
            frm.trigger("custom_sync_sub_batch_qty")
          })
        }

      }
    }

    // AUTO TRIGGER SYCN SUB BATCH/ CUSTOM SUBMIT WHEN OPENING MANUFACTURE ENTRY
    if(frm.is_dirty() && frm.is_new() && frm.get_field("custom_job_card_reference").value && frm.get_field("stock_entry_type").value==="Manufacture" && frm.doc.custom_quick_entry.length>0){
      frm.trigger("custom_submit")
    }
  },

  after_save: function (frm) {
    if (frm.doc.stock_entry_type == "Manufacture") {
      let sum = 0;
      for (let item of frm.doc.items) {
        if (item.is_finished_item) {
          sum += item.qty;
        }
      }
      if (frm.doc.fg_completed_qty) {
        if (sum < frm.doc.fg_completed_qty || sum > frm.doc.fg_completed_qty) {
          frappe.msgprint(
            `The required Finished Good qty is ${frm.doc.fg_completed_qty} and the entered qty is ${sum}`
          );
        }
      }
    }
  },

  custom_sync_sub_batch_qty: async function (frm) {
    await frappe.call({
      freeze:true,
      freeze_message :"Fetching Batches...",
      method:
        "tcb_manufacturing_customizations.doc_events.stock_entry.show_batches",
      args: {
        docname: frm.doc.name,
      },
      callback:(r)=>{
        if(r.message){
          frappe.dom.unfreeze()
          frm.reload_doc()
        }
      }
    });

  },

  custom_submit: async function (frm) {

    let grouped = frm.doc.custom_quick_entry.reduce((index, entry) => {
      let key = entry.item;
      if (!index[key]) {
        index[key] = [];
      }
      index[key].push(entry);
      return index;
    }, {});
    // METHOD DUPLICATE THE ROW
    for (let item_code in grouped) {
      let exist = frm.doc.items.find((i) => i.item_code == item_code);
      if (exist) {
        let count = frm.doc.items.filter(
          (c) => c.item_code == item_code
        ).length;
        let quick_entry = grouped[item_code].length;
        let copies_needed = quick_entry - count;
        if (copies_needed > 0) {
          let row = exist.name;
          for (let i = 0; i < copies_needed; i++) {
            // we got the name of the row we want to duplicate via this
            let grid_row = frm.fields_dict["items"].grid.grid_rows.find(
              (rows) => rows.doc.name == row
            );
            // method present at -> frappe/frappe/public/js/frappe/form/grid_row.js
            // (show, below, duplicate)
            grid_row.insert(false, true, true);
          }
        }

        let entry = grouped[item_code];
        let item_rows = frm.doc.items.filter((j) => j.item_code == item_code);
        for (let i = 0; i < entry.length; i++) {
          if (item_rows[i]) {
              // (item_rows[i].qty = entry[i].machine_consumption > 0 ? entry[i].machine_consumption : (entry[i].qty > 0 ?entry[i].qty : item_rows[i].qty) ),
              // WORKS THIS WAY IN PT ENTRIES
              (item_rows[i].qty = (entry[i].qty > 0 ?entry[i].qty : item_rows[i].qty) ),
              // for new slitec functionality- fetch the slitec rolls cut length
              (item_rows[i]).custom_slitec_roll_cutlengths = entry[i].slitec_roll_cut_lengths ? entry[i].slitec_roll_cut_lengths : "",
              (item_rows[i].custom_sub_batch = entry[i].sub_batch || ""),
              (item_rows[i].batch_no = entry[i].batch || ""),
              (item_rows[i].s_warehouse = entry[i].source_warehouse ? entry[i].source_warehouse : item_rows[i].s_warehouse),
              (item_rows[i].t_warehouse = entry[i].target_warehouse ? entry[i].target_warehouse : item_rows[i].t_warehouse);
              (item_rows[i].custom_machine_consumption_qty = entry[i].machine_consumption ? entry[i].machine_consumption : entry[i].qty);
              (item_rows[i].custom_manufactured_good_qty = entry[i].produced_good_qty ? entry[i].produced_good_qty :"")
          }
        }
      }

     
    }

    // REMOVE WASTAGE ITEMS FROM TABLE
    frm.refresh_field("items");
    
    await new Promise(resolve => setTimeout(resolve, 100));

    // REMOVE UNNECESSARY WASTAGE
    if (frm.doc.custom_wastage_from_job_card.length > 0) {
        let wastage_items = frm.doc.custom_wastage_from_job_card.map((item) => item.item);
        
        let items_to_remove = [];
        
        for (let i = frm.doc.items.length - 1; i >= 0; i--) {
            let row = frm.doc.items[i];
            if (row.is_scrap_item && !wastage_items.includes(row.item_code)) {
                items_to_remove.push(row.name);
            }
        }
        
        items_to_remove.forEach(row_name => {
            let grid_row = frm.fields_dict.items.grid.grid_rows_by_docname[row_name];
            if (grid_row) {
                grid_row.remove();
            }
        });
        
        frm.refresh_field("items");
    }


    // DO NOT SHOW ANY ITEM INCASE OF NO SCRAP OR WASTAGE ITEMS
    if (frm.doc.custom_wastage_from_job_card.length === 0) {
        
        let items_to_remove = [];
        
        for (let i = frm.doc.items.length - 1; i >= 0; i--) {
            let row = frm.doc.items[i];
            if (row.is_scrap_item) {
                items_to_remove.push(row.name);
            }
        }
        
        items_to_remove.forEach(row_name => {
            let grid_row = frm.fields_dict.items.grid.grid_rows_by_docname[row_name];
            if (grid_row) {
                grid_row.remove();
            }
        });
        
        frm.refresh_field("items");
    }

    await frm.save();
  },


  refresh: function (frm) { 

    // REMIND THE USER TO CONFIRM THE BATCHES
    frm.set_intro(`<i>REMEMBER TO CONFIRM THE BATCHES YOU'VE SELECTED</i>`,"blue")


    // conditionally hide the sync batch button
    if(frm.doc.stock_entry_type==="Manufacture"){
      frm.set_df_property("custom_sync_sub_batch_qty","hidden",1)
    }


    if (frm.doc.stock_entry_type == "Spares Transfer"  || frm.doc.stock_entry_type =="Spares Consumption") {
      setup_serial_filter(frm);
    }

    toggle_properties_workstation_consumables_spares(frm);

    
    if (frm.doc.docstatus == 1) {
      frappe.call({
        method:
          "tcb_manufacturing_customizations.doc_events.stock_entry.set_sb_after_submit",
        args: {
          docname: frm.doc.name,
        },
      });
    }
    frm.fields_dict["custom_quick_entry"].grid.get_field(
      "source_warehouse"
    ).get_query = function (doc, cdt, cdn) {
      return {
        filters: {
          is_group: 0,
        },
      };
    };
    frm.fields_dict["custom_quick_entry"].grid.get_field("item").get_query =
      function (doc, cdt, cdn) {
        return {
          filters: {
            is_stock_item: 1,
          },
        };
      };


    const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
if (frm.doc.docstatus == 0 && frm.doc.stock_entry_type == "Manufacture") {
    if (frm.doc.bom_no) {
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "BOM",
                name: frm.doc.bom_no,
            },
            callback: (r) => {
                if (r.message.routing == "Slitting") {
                    frm.add_custom_button("Slit Final Product", () => {
                        frappe.call({
                            method: "tcb_manufacturing_customizations.doc_events.stock_entry.set_finished_goods",
                            args: {
                                docname: frm.doc.name,
                            },
                            callback: async function (r) {
                                if (!r.exc && r.message) {
                                    const {
                                        finished_items,
                                        fabric_qtys,
                                        div,
                                        sub_batch,
                                        cut_lengths
                                    } = r.message;
                                    
                                    const finished_item = finished_items[0];
                                    let finished_dict = [];

                                    // Process each fabric item
                                    fabric_qtys.forEach((qty, index) => {
                                        let batch = sub_batch[index];
                                        let cutlength_master = cut_lengths[index];
                                        
                                        // Parse cut lengths
                                        let separated_lengths = cutlength_master
                                            .trim()
                                            .split(",")
                                            .filter(n => n)
                                            .map(n => parseFloat(n.trim()));
                                        
                                        // Create entries for each cut length
                                        separated_lengths.forEach((cutLength, j) => {
                                            let letter = letters[j];
                                            
                                            // Create entries for each division
                                            for (let i = 0; i < div; i++) {
                                                let sub_batch_name = `${batch}-${letter}${i + 1}`;
                                                
                                                finished_dict.push({
                                                    qty: cutLength,
                                                    sub_batch: sub_batch_name
                                                });
                                            }
                                        });
                                    });

                                    // Add all rows to items table
                                    finished_dict.forEach(item_data => {
                                        let new_row = frm.add_child("items");
                                        
                                        // Copy all fields from finished_item except specific ones
                                        Object.keys(finished_item).forEach((key) => {
                                            if (
                                                key !== "name" &&
                                                key !== "idx" &&
                                                key !== "qty" &&
                                                key !== "serial_and_batch_bundle"
                                            ) {
                                                new_row[key] = finished_item[key];
                                            }
                                        });
                                        
                                        new_row.qty = item_data.qty;
                                        new_row.custom_sub_batch = item_data.sub_batch;
                                    });

                                    // Remove original finished item
                                    let remove_index = frm.doc.items.findIndex(
                                        (row) => row.name == finished_items[0].name
                                    );
                                    if (remove_index != -1) {
                                        frm.doc.items.splice(remove_index, 1);
                                    }
                                    frm.remove_custom_button("Slit Final Product")
                                    frm.refresh_field("items");
                                }
                            },
                        });
                    });
                }
            },
        });
    }
    frm.trigger("refresh_serial_batch_popup");
}

    if (frm.doc.docstatus == 1) {
          // check_stock_entry_submitted(frm)

      if (frm.doc.stock_entry_type == "Spares Transfer") {
        frm.add_custom_button(__("Consume Spares"), async function () {
          const stk_entry_type = "Spares Consumption";
          let items_with_qty = await check_stock_entry_submitted(frm)
          const to_warehouse = ""
          const from_warehouse = frm.doc.target_warehouse; // changed because it will be the soruce warehouse
          const custom_default_workstation = frm.doc.custom_default_workstation;

          let all_consumable_spare_rows = []

          for (const item of frm.doc.items) {
            if (item.item_group == "Consumable Spares" || item.item_group == "Store Spares") {
              row = {}
              row = { ...item }
              row.t_warehouse = ""

              // if ((item.item_code in items_with_qty)) {
              if (item.item_code in items_with_qty) {
                  row.qty = row.qty - items_with_qty[item.item_code];
                  if (row.qty == 0){
                    continue;
                  }
              }
              row.s_warehouse = item.t_warehouse
              all_consumable_spare_rows.push(row)
            }
          };
          
          if (all_consumable_spare_rows.length == 0) {
            frappe.throw(`
                    No Consumable or Store Spares found to Consume.<br><br>
                    Possible Reasons:<br>
                    • All quantities have already been consumed<br>
                    • No valid Consumable/Store items present in this Stock Entry
                `);
            return
          }
          // const install_date = frm.doc.date_of_installation;
          // Create and setup Stock Entry
          if (all_consumable_spare_rows.length > 0){
            const stock_entry_name = await createStockEntry(
              stk_entry_type,
              to_warehouse,
              from_warehouse,
              frm.doc.name,
              custom_default_workstation,
              all_consumable_spare_rows
            );
            
            if (!stock_entry_name) {
              frappe.msgprint("Failed to create Stock Entry");
              return;
            }
          }

        }, __("Create"))

        frm.add_custom_button(__("Return Spares"), async function () {
          const stk_entry_type = "Material Transfer";
          let items_with_qty = await check_stock_entry_submitted(frm)
          const to_warehouse = frm.doc.source_warehouse
          const from_warehouse = frm.doc.target_warehouse; // changed because it will be the soruce warehouse
          const custom_default_workstation = frm.doc.custom_default_workstation;

          let all_consumable_spare_rows = []
          for (const item of frm.doc.items) {
            if (item.item_group == "Consumable Spares" || item.item_group == "Store Spares") {
              // console.log('eeeiteemmmmmm==', item)
              row = {}
              row = { ...item }
              row.t_warehouse = item.s_warehouse
              row.s_warehouse = item.t_warehouse
              if (item.item_code in items_with_qty) {
                  row.qty = row.qty - items_with_qty[item.item_code];
                  if (row.qty == 0){
                    continue;
                  }
              }
              all_consumable_spare_rows.push(row)
            }
          };
          if (all_consumable_spare_rows.length == 0) {
            frappe.throw(`
                    No Consumable or Store Spares found to return.<br><br>
                    Possible Reasons:<br>
                    • All quantities have already been consumed<br>
                    • No valid Consumable/Store items present in this Stock Entry
                `);
            return
          }
          // console.log('================ here is the all rows with consumable spares =', all_consumable_spare_rows)
          // const install_date = frm.doc.date_of_installation;
          // Create and setup Stock Entry
          if (all_consumable_spare_rows.length > 0){
            const stock_entry_name = await createStockEntry(
              stk_entry_type,
              to_warehouse,
              from_warehouse,
              frm.doc.name,
              custom_default_workstation,
              all_consumable_spare_rows
            );

            if (!stock_entry_name) {
              frappe.msgprint("Failed to create Stock Entry");
              return;
            }
          }

        }, __("Create"))
      }

    }
  },



  custom_default_workstation: async function (frm) {
    if (frm.doc.custom_default_workstation){
    frm.doc.items.forEach(row => {
      row.custom_workstation = frm.doc.custom_default_workstation;
    });
    frm.refresh_field("items");
    workstation_doc = await frappe.db.get_doc("Workstation",frm.doc.custom_default_workstation)
    workstation_warehouse = workstation_doc.warehouse
    if (workstation_warehouse){
      frm.set_value('to_warehouse',workstation_warehouse)
    }
    else {
      frappe.msgprint("Warehouse Not Configured In This Workstation")
    }
  }
  }
  ,

  stock_entry_type: async function (frm) {
    toggle_properties_workstation_consumables_spares(frm);
    if (frm.doc.stock_entry_type === "Spares Transfer") {
    const spares_settings_doc = await frappe.db.get_doc('Workstation Spares Settings','Workstation Spares Settings',);
    const spares_transfer_source_warehouse_name =  spares_settings_doc.default_spares_transfer_source_warehouse
    
    if (!spares_transfer_source_warehouse_name){
      frappe.throw({
          title: `Default Spares Transfer Source Warehouse Missing`,
          message: `
              <b>Spares Transfer Source Warehouse is not configured!</b><br><br>
              Please set the <b>Default Spares Transfer Source Warehouse</b> in the 
              <b>Workstation Spares Settings</b> before performing this action.<br><br>
              👉 <a href="/app/workstation-spares-settings/Workstation%20Spares%20Settings" 
              target="_blank" 
              style="font-weight:600; color:#2980b9;">
                  Open Workstation Spares Settings
              </a>
          `
      });
    }

    else{
      frm.set_value('from_warehouse',spares_transfer_source_warehouse_name)
    }
  }

  frm.trigger("refresh_serial_batch_popup");
  },

  
  on_submit:function(frm){

    // location.reload()
    // Route to JOB CARD IF EXISTS. 
   if(frm.doc.job_card){
     frappe.confirm("Done the Entry, Do you want to return to Job Card?",()=>{
       if(frm.doc.job_card){
         frappe.set_route("Form","Job Card",frm.doc.job_card)
        }
      })
    }
    
        
        // console.log('---here is the on sumbit --',frm)
        if (frm.doc.custom_stock_entry_reference === "Workstation Spare Parts"){
            // console.log('eeeifffffffffffffffffffeyeyey',frm.doc.posting_date)
            frappe.call({
                method:"tcb_manufacturing_customizations.doc_events.stock_entry.set_serial_number_after_submit",
                args:{
                        docname:frm.doc.name
                    },
                    callback:(r)=>{
                        // console.log(r)
                    }
            },)
        }
        
        else if (frm.doc.stock_entry_type === "Spares Transfer" || frm.doc.stock_entry_type === "Spares Consumption"){
            frappe.call({
                method:"tcb_manufacturing_customizations.doc_events.stock_entry.create_workstation_spares_doc_entries",
                args:{
                        docname:frm.doc.name
                    },
                    freeze: true, 
                    freeze_message: __("Creating Spare Doc Entries and Spare Move History..."),
                    callback:(r)=>{
                        // console.log(r)
                    }
            },)
            // console.log('eeeeyeyey',frm.doc.posting_date)
        }
},

  refresh_serial_batch_popup: (frm)=>{
    if(frm.doc.stock_entry_type != "Spares Transfer" && frm.doc.stock_entry_type != "Spares Consumption"){
      erpnext.stock.select_batch_and_serial_no = (frm, item) => {
        let path = "assets/erpnext/js/utils/serial_no_batch_selector.js";

        frappe.db.get_value("Item", item.item_code, ["has_batch_no", "has_serial_no"]).then((r) => {
          if (r.message && (r.message.has_batch_no || r.message.has_serial_no)) {
            item.has_serial_no = r.message.has_serial_no;
            item.has_batch_no = r.message.has_batch_no;
            item.type_of_transaction = item.s_warehouse ? "Outward" : "Inward";

            new erpnext.SerialBatchPackageSelector(frm, item, (r) => {
              if (r) {
                frappe.model.set_value(item.doctype, item.name, {
                  serial_and_batch_bundle: r.name,
                  use_serial_batch_fields: 0,
                  basic_rate: r.avg_rate,
                  qty:
                    Math.abs(r.total_qty) /
                    flt(item.conversion_factor || 1, precision("conversion_factor", item)),
                });
              }
            });
          }
        });
      };

      frm.events.refresh(frm)
    }
    else{
      erpnext.stock.select_batch_and_serial_no = (a,b) => {};
    }
  },
});

async function check_stock_entry_submitted(frm) {
  // console.log('=========== doc name ==',stock_entry_docname)
  let linked_stock_entries_without_submitted = await frappe.db.get_list('Stock Entry', {
    filters: {
      // stock_entry_type: stock_entry_type,
      'docstatus': 0,
      'custom_stock_entry_reference': frm.doc.name
    },
    fields: ["name", "docstatus"],
    order_by: 'modified asc',
    limit: 1
  });

  if (linked_stock_entries_without_submitted && linked_stock_entries_without_submitted.length > 0) {
    let entry = linked_stock_entries_without_submitted[0].name;
    frappe.throw(`
            <b>Stock Entry Already Exists!</b><br><br>
            A draft Stock Entry (<b>${entry}</b>) is already created for this document.<br>
            Please submit or cancel that entry before creating a new one.
        `);
    return;
  }
  else {
    let linked_stock_entries = await frappe.db.get_list('Stock Entry', {
      filters: {
        // stock_entry_type: stock_entry_type,
        'docstatus': ['!=', 2],
        'custom_stock_entry_reference': frm.doc.name
      },
      fields: ["name", "docstatus"],
      order_by: 'modified asc',
      // limit: 1
    });

    // for (let item of frm.doc.items){
    //   if(frm.doc.docstatus == 1){
    // forEach.linked_stock_entries( entry =>{
    // console.log('-===a ll linked linked_stock_entries==', linked_stock_entries)
    items_with_qty = {}
    for (const entry of linked_stock_entries) {
        if (entry.docstatus == 1) {
        let stock_items = await frappe.db.get_list("Stock Entry Detail", {
          filters: {
            parent: entry.name
          },
          fields: ["name", "item_code", "s_warehouse", "item_name", "qty", "t_warehouse", "item_code"]
        });
        // console.log("sotck eit3ess=====", stock_items);

        if (stock_items) {
          for (const item of stock_items) {
            if (item.item_code) {

              for (const i of frm.doc.items) {
                // console.log(' for i   enterdd ====', i.item_code, " === qty ==", i.qty)
                // console.log(' for i    i - t warehosue ====', i.t_warehouse, " === item.s_warehouse  ==", item.s_warehouse)

                // if (item.item_code === i.item_code && item.s_warehouse === i.t_warehouse ){
                if (item.item_code === i.item_code && i.t_warehouse == item.s_warehouse) {
                  // console.log(' final condition enterdd ====', i.item_code, " === qty ==", i.qty)
                  if (!(item.item_code in items_with_qty)) {
                    let quantity = 0
                    quantity = item.qty
                    // console.log('==ifffff=== yee   qwuantity  --', quantity)
                    items_with_qty[item.item_code] = quantity
                    // console.log(' h==ifff== here is the itemwith qety ==', items_with_qty)
                  }
                  else if ((item.item_code in items_with_qty)) {
                    // console.log('==elsesseeee=== yee   qwuantity  --', quantity)
                    items_with_qty[item.item_code] += item.qty
                    // console.log(' h==eisesleleleee== here is the itemwith qety ==', items_with_qty)
                  }
                }
              }

            }

          }
          // console.log(' h==== eneddddddddddddddd qety ==', items_with_qty)

        }

      }

    };

  }
  return items_with_qty
}


async function createStockEntry(
  entry_type,
  to_warehouse,
  from_warehouse,
  reference,
  custom_default_workstation,
  item_rows
) {
  return new Promise((resolve, reject) => {
    frappe.model.with_doctype('Stock Entry', () => {
      const stock_entry = frappe.model.get_new_doc('Stock Entry');

      stock_entry.stock_entry_type = entry_type;
      stock_entry.to_warehouse = to_warehouse;
      stock_entry.from_warehouse = from_warehouse;
      stock_entry.custom_default_workstation = custom_default_workstation;
      stock_entry.custom_stock_entry_reference = reference;

      // stock_entry.posting_date = posting_date;
      // stock_entry.set_posting_time = 1;
      // stock_entry.custom_stock_entry_reference = reference_doctype;


      item_rows.forEach(item => {
        const item_row = frappe.model.add_child(stock_entry, 'Stock Entry Detail', 'items');
        item_row.item_code = item.item_code;
        item_row.t_warehouse = item.t_warehouse;
        item_row.s_warehouse = item.s_warehouse;
        item_row.custom_workstation = item.custom_workstation;
        item_row.qty = item.qty;
        item_row.transfer_qty = item.transfer_qty;
        item_row.uom = item.uom;
        item_row.stock_uom = item.stock_uom;
        item_row.conversion_factor = item.conversion_factor;
        // item_row.against_stock_entry = item.name;

        // console.log("herere0============== otem rwoww ",item_row)
        // item_row.serial_no = serial_no
      });

      frappe.call({
        method: 'frappe.client.save',
        args: {
          doc: stock_entry
        },
        callback: function (r) {
          if (r.message) {
            frappe.set_route("Form", "Stock Entry", r.message.name);
            resolve(r.message.name);
          } else {
            reject(new Error("Failed to save Stock Entry"));
          }
        },
        error: function (err) {
          reject(err);
        }
      });
    });
  });
}


function toggle_properties_workstation_consumables_spares(frm) {
  if (frm.doc.stock_entry_type === "Spares Consumption") {
    // console.log('here is the ====',frm.doc.custom_default_workstation)
    frm.fields_dict.items.grid.toggle_display("t_warehouse", 0)
    frm.fields_dict.items.grid.toggle_display("custom_workstation", 1)
    frm.fields_dict.items.grid.toggle_reqd("custom_workstation", 1)

    //  filter on item field
    frm.fields_dict.items.grid.get_field("item_code").get_query = function () {
      return {
        filters: {
          item_group: ["like","%spare%"]
        }
      };
    };

    frm.refresh_field("items");
  }
  else if (frm.doc.stock_entry_type === "Spares Transfer") {
    frm.fields_dict.items.grid.toggle_display("t_warehouse", 1)
    frm.fields_dict.items.grid.toggle_display("custom_workstation", 1)
    frm.fields_dict.items.grid.toggle_reqd("custom_workstation", 1)
    frm.fields_dict.items.grid.get_field("item_code").get_query = function () {
                        return {
                            filters: {
                            item_group: ["like","%spares%"]
                            }
                        };
    };
    frm.refresh_field("items");

  }
  else {
    // console.log('here sithe this sss==',frm.fields_dict.items.grid.toggle_display("custom_workstation",0))
    frm.fields_dict.items.grid.toggle_display("custom_workstation", 0)
    frm.fields_dict.items.grid.toggle_display("t_warehouse", 1)
    frm.fields_dict.items.grid.toggle_reqd("custom_workstation", 0)
    frm.fields_dict.items.grid.get_field("item_code").get_query = function () {
      return {};
    };
    frm.refresh_field("items");
  }

}



frappe.ui.form.on("Set Batch for Items", {
  sub_batch: function (frm, cdt, cdn) {
    let row = locals[cdt][cdn]
    frappe.call({
      method: "tcb_manufacturing_customizations.doc_events.stock_entry.get_sub_batch_qty",
      args: {
        sub_batch: row.sub_batch,
        warehouse: row.source_warehouse,
        item: row.item
      },
      callback: (r) => {
        if (r.message) {
          frappe.model.set_value(cdt, cdn, "qty", r.message[0])
          frappe.model.set_value(cdt, cdn, "batch", r.message[1])
          frm.refresh_field("custom_quick_entry")
        }
      }
    })
  }
})
function setup_serial_filter(frm) {
    frm.set_query("custom_select_serial_no", "items", function(doc, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row && row.item_code && row.qty == 1 && (doc.stock_entry_type =="Spares Transfer" || doc.stock_entry_type =="Spares Consumption")) {
            return {
                filters: {
                    'item_code': row.item_code,
                    "warehouse":row.s_warehouse,
                    'status': 'Active'

                }
            };
        }
        else {
            return {
                filters: {
                    'item_code': '',
                    // 'status': 'Active'
                }
            };
        }
    });
}



