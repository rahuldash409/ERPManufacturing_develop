function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function validate_delivery_date(frm) {
    const today_date = new Date();
    const requested_delivery_date = frm.urgent_dialog_values.requested_delivery_date;
    let days_btw_today_and_request = (frappe.datetime.get_day_diff(requested_delivery_date, today_date)) + 1;
    const required_days = frm.doc.process_days;
    console.log('this is the frappe. doc   - ', frm.doc)
    console.log('this is the process days - ', frm.doc.process_days)
    console.log('this is the shipping dasyss - ', frm.urgent_dialog_values.shipping_transit_time_days)
    console.log('this is the requreed days - ', required_days)
    console.log('this is the days btw dates - ', days_btw_today_and_request)
    if (required_days > days_btw_today_and_request) {
        frappe.msgprint({
            title: __('⚠️ Delivery Date Too Early'),
            message: __(
                "Requested delivery date is too early.<br><br>" +
                "Required production + shipping time: <b>{0} working days</b><br>" +
                "Days available until requested date: <b>{1} days</b><br><br>" +
                "Please choose a later delivery date or reduce the order quantity.<br><br>"+
                "<i>Note: This calculation are based on working days only (holidays excluded).</i><br>",
                [required_days, days_btw_today_and_request]
            ),
            indicator: 'red',
            primary_action: {
            label: __('OK'),
            action: () => {
                cur_dialog.hide();  
            }
        }
        });
    } else {
        frappe.msgprint({
            title: __('✅ Delivery Date Feasible'),
            message: __(
                "This order can be delivered on the requested date.<br><br>" +
                "Required time: <b>{0} working days</b><br>" +
                "Available time: <b>{1} days</b><br><br>" +
                "<i>Note: This calculation are based on working days only (holidays excluded).</i>",
                [required_days, days_btw_today_and_request]
            ),
            indicator: 'green',
            primary_action: {
            label: __('OK'),
            action: () => {
                cur_dialog.hide();  
            }
        }
        });
    }
}


frappe.ui.form.on("Delivery Estimate", {
    order_priority: function (frm) {

        if (frm.doc.order_priority === 'Urgent') {

            let d = new frappe.ui.Dialog({
                title: 'Enter details',
                fields: [
                    {
                        label: 'Item',
                        fieldname: 'item',
                        fieldtype: 'Link',
                        options: 'Item',
                        reqd: 1,
                        onchange: async function () {
                            let item = d.get_value('item');
                            if (item) {
                                try {
                                    // get default BOM for this item
                                    let boms = await frappe.db.get_list('BOM', {
                                        filters: {
                                            item: item,
                                            is_default: 1
                                        },
                                        fields: ['name'],
                                        order_by: 'modified desc',
                                        limit: 1
                                    });

                                    if (boms && boms.length > 0) {
                                        d.set_value('bom', boms[0].name);
                                    } else {
                                        frappe.msgprint(__('No default BOM found for this item.'));
                                        d.set_value('bom', null);
                                        d.set_value('item', null);
                                    }
                                } catch (err) {
                                    console.error("Error fetching BOM:", err);
                                    frappe.msgprint(__('Error fetching BOM.'));
                                }
                            }
                        }
                    },
                    {
                        label: 'BOM',
                        fieldname: 'bom',
                        fieldtype: 'Link',
                        options: 'BOM',
                        reqd: 1
                    },
                    {
                        label: 'Item Quantity',
                        fieldname: 'item_quantity',
                        fieldtype: 'Float',
                        reqd: 1
                    },
                    {
                        label: 'Requested Delivery Date',
                        fieldname: 'requested_delivery_date',
                        fieldtype: 'Date',
                        reqd: 1,
                        onchange: async function () {
                            let date = d.get_value('requested_delivery_date');
                            if (date) {
                                const today = frappe.datetime.get_today(); // yyyy-mm-dd format
                                if (frappe.datetime.str_to_obj(date) < frappe.datetime.str_to_obj(today)) {
                                    frappe.msgprint({
                                        title: __('Invalid Date'),
                                        message: __('🚫 Requested Delivery Date cannot be in the past.'),
                                        indicator: 'red',
                                        primary_action: {
                                            action: () => {
                                                                cur_dialog.hide();  
                                                            },
                                            label: __('OK')
                                        }
                                    });
                                    d.set_value('requested_delivery_date', null); // clear invalid value
                                }
                            }
                        }
                    },
                    {
                        label: 'Shipping Transit Time (Days)',
                        fieldname: 'shipping_transit_time_days',
                        fieldtype: 'Float',
                        reqd: 1
                    },
                    {
                        label: 'Holiday List',
                        fieldname: 'holiday_list',
                        fieldtype: 'Link',
                        options: 'Holiday List'
                    }
                ],
                size: 'small', // small, large, extra-large 
                primary_action_label: 'Submit',
                primary_action: async function (values) {
                    frm.urgent_dialog_values = values;
                    if (frm.urgent_dialog_values) {
                        frm.doc.item_to_deliver = frm.urgent_dialog_values.item;
                        frm.doc.bom = frm.urgent_dialog_values.bom;
                        frm.doc.qty_to_deliver = frm.urgent_dialog_values.item_quantity;
                        frm.doc.shipping_transit_time_days = frm.urgent_dialog_values.shipping_transit_time_days;
                        frm.doc.holiday_list = frm.urgent_dialog_values.holiday_list;
                    }
                    
                    frappe.dom.freeze(__("Loading, please wait..."));
                    await frm.trigger("get_sales_orders");
                    await delay(500);
                    await frm.trigger("calculate_raw_materials");
                    await delay(500);
                    await frm.trigger("check_stock_availability");
                    await delay(500);
                    await frm.trigger("calculate_lead_time");
                    await delay(500);
                    await frm.trigger("calculate_procurement_lead_time");
                    await frm.trigger("get_item_wise_workstation");
                    await delay(500);
                    await frm.trigger("calculate_production_details");
                    await frm.trigger("get_employee_leave_list");
                    await delay(500);
                    await frm.trigger("calculate_delivery_date");
                    
                    d.hide();
                    await delay(100);
                    frappe.dom.unfreeze();
                    await frm.reload_doc();
                    await delay(200);
                    await validate_delivery_date(frm);
                }
            });
            d.show();
        }

    }
})