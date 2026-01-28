// DEV
frappe.ui.form.on("BOM", {
  after_save: function (frm) {
    set_excess_qty(frm);
    // bomExcessQty(frm);
  },
});

// function bomExcessQty(frm) {
//   if (frm.doc.custom_excess_material__required > 0) {
//     frm.doc.items.forEach((item) => {
//       if (item.bom_no) {
//         frappe.db.get_doc("BOM", item.bom_no).then((doc) => {
//           if (doc.custom_excess_material__required == 0) {
//             frappe.confirm(
//               `BOM Exists for ${item.item_code} that doesnt have Excess % Quantity Set, Do you want to create a new version for it?`,
//               () => {
//                 let new_doc = frappe.model.copy_doc(doc);

//                 frappe.call({
//                   method: "frappe.client.insert",
//                   args: { doc: new_doc },
//                   callback: (r) => {
//                     frappe.call({
//                       method: "frappe.client.set_value",
//                       args: {
//                         doctype: "BOM",
//                         name: r.message.name,
//                         fieldname: "custom_excess_material__required",
//                         value: frm.doc.custom_excess_material__required,
//                       },
//                       callback: async (r) => {
//                         // await frappe.set_route("Form","BOM",r.message.name)
//                         // setTimeout(()=>{
//                         // frm.save()
//                         // },500)
//                       },
//                     });
//                   },
//                   error: (err) => {
//                     console.log(err);
//                   },
//                 });
//               }
//             );
//           }
//         });
//       }
//     });
//   }
// }

// Possibility 2-> if the raw mats contain excess % then add that to final item
async function set_excess_qty(frm) {
  let excess_qty = 0;
  if (
    (frm.doc.custom_excess_material__required == 0 ||
      frm.doc.custom_excess_material__required == "" || frm.doc.custom_excess_material__required < excess_qty) &&
    frm.doc.docstatus == 0
  ) {
    if (frm.doc.items && frm.doc.items.length > 0) {
      let promises = frm.doc.items.map((item) => {
        if (item.bom_no) {
          return frappe.db.get_doc("BOM", item.bom_no).then((i) => {
            if (i.custom_excess_material__required > 0) {
              excess_qty += i.custom_excess_material__required;
            }
          });
        } else {
          return Promise.resolve();
        }
      });

      await Promise.all(promises);
    }
  }
  if (excess_qty > 0 && excess_qty > frm.doc.custom_excess_material__required) {
    frappe.confirm(
      "The raw materials contain excess quantity, do you want to sum that and add to final item?",
      () => {
        frm.set_value("custom_excess_material__required", excess_qty);
      }
    );
  }
}

// ORIGINAL (PUSHED)-
// frappe.ui.form.on("BOM", {
//     after_save: function(frm) {
//         bomExcessQty(frm)
//     }
// });

// function bomExcessQty(frm){
//     if (frm.doc.custom_excess_material__required > 0) {
//             frm.doc.items.forEach((item) => {
//                 if (item.bom_no) {

//                     frappe.db.get_doc("BOM", item.bom_no).then(doc => {

//                         if(doc.custom_excess_material__required==0){
//                             let new_doc = frappe.model.copy_doc(doc);

//                         frappe.call({
//                             method: "frappe.client.insert",
//                             args: { doc: new_doc },
//                             callback: (r) => {
//                                 frappe.call({
//                                     method:"frappe.client.set_value",
//                                     args:{
//                                         doctype:"BOM",
//                                         name:r.message.name,
//                                         fieldname:"custom_excess_material__required",
//                                         value:frm.doc.custom_excess_material__required
//                                     },
//                                     callback: async (r)=>{
//                                         await frappe.set_route("Form","BOM",r.message.name)
//                                         setTimeout(()=>{
//                                         frm.save()
//                                         },1000)
//                                     }
//                                 })
//                             },
//                             error: (err) => {
//                                 console.log(err);
//                             }
//                         });
//                         }
//                     });
//                 }
//             });
//         }
// }
