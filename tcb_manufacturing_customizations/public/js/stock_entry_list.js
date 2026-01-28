frappe.listview_settings['Stock Entry'] = {
    onload: function(listview) {
        // listview.add_field = {
        //     'item' : 'Item' 
        // }
        // var custom_filter_df = {
        //     fieldname: "child_table_filter_field",
        //     label: __("Child Table Filter Label"), // Replace with your label
        //     fieldtype: "Link",
        //     options : "Item", // Can be Link, Select, etc. as needed
        //     onchange: function() {
        //         // When the custom filter value changes, refresh the list view
        //         listview.refresh();
        //     },
        // };
        // listview.page.add_field(custom_filter_df);
        // $(("list_view_custom_filter", {
        //     label: __("Item Code Filter"),
        //     fieldname: "custom_item_code_filter"
        // })).appendTo(listview.page.fields_area);

        // Bind the change event to refresh the list
        // listview.page.fields_area.find("#custom_item_code_filter").on('change', function() {
        //     listview.refresh();
        // });
        // listview.page.filter_area.add_field([['Stock Entry Detail', 'item_code', '=', '']]);
        // Child table field filter add karna
        // listview.page.add_field({
        //     fieldname: 'item_code_filter',
        //     label: __('Item Code'),
        //     fieldtype: 'Link',
        //     options: 'Item',
        //     change: function() {
        //         let value = this.get_value();
        //         if (value) {
        //             listview.filter_area.add([[
        //                 'Stock Entry Detail', 'item_code', '=', value
        //             ]]);
        //         }
        //     }
        // });
    }
};
