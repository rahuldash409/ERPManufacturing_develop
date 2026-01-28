frappe.ui.form.on("Workstation", {
    refresh: function(frm) {
        // frappe.msgprint('eleleleleyeeleeley')
        // frm.fields_dict["custom_workstation_spare_parts"].grid.get_field("spare_part").get_query = function(doc, cdt, cdn) {
        //     return {
        //         filters: {
        //             "item_group": "Spare Parts"
        //         }
        //     };
        // };
        // calculate_service_life_days(frm, cdt, cdn);
        // frm.set
        // frm.fields_dict["custom_workstation_spare_parts"].grid.get_row_class = function(frm, cdt, cdn) {
        //     let row = locals[cdt][cdn];
        //     let bgColor = '';
        //     if (row.status === "In Use") {
        //         bgColor = '#c9f7d4';
        //       a  // return "row-green";
        //     } else if (row.status === "Disposed") {
        //         bgColor = '#f8d7da';
        //         // return "row-red";
        //     } else if (row.status === "Under Maintenance") {
        //         bgColor = '#fff3cd';
        //         // return "row-orange";
        //     }
        //     if (bgColor) {
        //         row = `<span style="background-color:${bgColor}; padding:3px; display:block;">${value}</span>`;
        //     }
        //     // if (data && data.status) {
        //     // let bgColor = '';
            
        //     // if (data.status === "In Use") {
        //     //     bgColor = '#d4edda';
        //     // }
        //     // else if (data.status === "Disposed") {
        //     //     bgColor = '#f8d7da';
        //     // }
        //     // else if (data.status === "Under Maintenance") {
        //     //     bgColor = '#fff3cd';
        //     // }
            
        //     // if (bgColor) {
        //     //     value = `<span style="background-color:${bgColor}; padding:3px; display:block;">${value}</span>`;
        //     // }
        // };
    }
});

// frappe.ui.form.on("Workstation Spare Parts", {
//     spare_part: function(frm, cdt, cdn) {
//         calculate_service_life_days(frm, cdt, cdn);
//     },
//     date_of_installation: function(frm, cdt, cdn) {
//         calculate_service_life_days(frm, cdt, cdn);
//     },
//     dispose_replacement_date: function(frm, cdt, cdn) {
//         calculate_service_life_days(frm, cdt, cdn);
//     }
// });


// function calculate_service_life_days(frm, cdt, cdn) {
//     let row = locals[cdt][cdn];
//         // frappe.msgprint('heeeyeeyeeyey')
//     // console.log('here is the row . installaiton date- ',row.date_of_installation)

//     if (row.date_of_installation && row.dispose_replacement_date) {
//         let start = frappe.datetime.str_to_obj(row.date_of_installation);
//         let end = frappe.datetime.str_to_obj(row.dispose_replacement_date);

//         if (start && end) {
//             if (end >= start) {
//                 let diff_days = frappe.datetime.get_day_diff(end, start);
//                 row.service_life_days = diff_days;
//                 row.status = "Disposed"
//             } else {
//                 frappe.msgprint({
//                     title: __("Invalid Dates"),
//                     message: __("Dispose / Replacement Date cannot be earlier than Date of Installation."),
//                     indicator: "red"
//                 });
//                 row.service_life_days = 0;
//                 row.dispose_replacement_date = null;
//             }
//             frm.refresh_field("custom_workstation_spare_parts");
//         }
//     }
// }
