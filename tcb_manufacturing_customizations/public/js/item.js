frappe.ui.form.on("Spare Rack Locations",{
    rack : function (frm, cdt, cdn) { combine_rack_location(frm, cdt, cdn) },
    rack_column  : function (frm, cdt, cdn) { combine_rack_location(frm, cdt, cdn) },
    rack_row : function (frm, cdt, cdn) { combine_rack_location(frm, cdt, cdn) }

})

function combine_rack_location(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let location = `${row.rack || ""}-${row.rack_column || ""}${row.rack_row || ""}`
    row.combined_location = location
}
