frappe.pages['sales-flow-dashboard'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Sales Flow Dashboard',
        single_column: true
    });

    // Load page content
    $(frappe.render_template('sales_flow_dashboard')).appendTo(page.body);

    // Initialize the dashboard
    new SalesFlowDashboard(page);
};

class SalesFlowDashboard {
    constructor(page) {
        this.page = page;
        this.$wrapper = $(page.body);
        this.filters = {};

        this.init();
    }

    init() {
        this.setup_filters();
        this.bind_events();
        this.load_data();
    }

    setup_filters() {
        const me = this;

        // Company filter
        this.company_field = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                options: 'Company',
                fieldname: 'company',
                placeholder: 'Select Company',
                default: frappe.defaults.get_user_default('Company')
            },
            parent: this.$wrapper.find('#company-filter'),
            render_input: true
        });
        this.company_field.set_value(frappe.defaults.get_user_default('Company'));

        // From Date filter
        this.from_date_field = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Date',
                fieldname: 'from_date',
                placeholder: 'From Date',
                default: frappe.datetime.month_start()
            },
            parent: this.$wrapper.find('#from-date-filter'),
            render_input: true
        });
        this.from_date_field.set_value(frappe.datetime.month_start());

        // To Date filter
        this.to_date_field = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Date',
                fieldname: 'to_date',
                placeholder: 'To Date',
                default: frappe.datetime.month_end()
            },
            parent: this.$wrapper.find('#to-date-filter'),
            render_input: true
        });
        this.to_date_field.set_value(frappe.datetime.month_end());
    }

    bind_events() {
        const me = this;

        // Refresh button
        this.$wrapper.find('#refresh-btn').on('click', () => {
            me.load_data();
        });

        // Card click to navigate with filters
        this.$wrapper.on('click', '.flow-card', function() {
            const doctype = $(this).data('doctype');
            if (doctype) {
                const filters = me.get_list_filters(doctype);
                frappe.set_route('List', doctype, filters);
            }
        });

        // Pending item click
        this.$wrapper.on('click', '.pending-item, .recent-item', function() {
            const doctype = $(this).data('doctype');
            const name = $(this).data('name');
            if (doctype && name) {
                frappe.set_route('Form', doctype, name);
            }
        });

        // Customer item click
        this.$wrapper.on('click', '.customer-item', function() {
            const customer = $(this).data('customer');
            if (customer) {
                frappe.set_route('Form', 'Customer', customer);
            }
        });
    }

    get_list_filters(doctype) {
        const from_date = this.from_date_field.get_value();
        const to_date = this.to_date_field.get_value();
        const company = this.company_field.get_value();

        // Different doctypes have different date field names
        const date_field_map = {
            'Quotation': 'transaction_date',
            'Sales Order': 'transaction_date',
            'Release Order': 'posting_date',
            'Delivery Note': 'posting_date'
        };

        const date_field = date_field_map[doctype] || 'creation';
        const filters = {};

        if (from_date) {
            filters[date_field] = ['>=', from_date];
        }
        if (to_date) {
            filters[date_field] = from_date
                ? ['between', [from_date, to_date]]
                : ['<=', to_date];
        }
        if (company) {
            filters['company'] = company;
        }

        return filters;
    }

    show_loading() {
        this.$wrapper.find('#loading-overlay').addClass('active');
    }

    hide_loading() {
        this.$wrapper.find('#loading-overlay').removeClass('active');
    }

    load_data() {
        const me = this;
        me.show_loading();

        frappe.call({
            method: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.page.sales_flow_dashboard.sales_flow_dashboard.get_dashboard_data',
            args: {
                from_date: me.from_date_field.get_value(),
                to_date: me.to_date_field.get_value(),
                company: me.company_field.get_value()
            },
            callback: function(r) {
                me.hide_loading();
                if (r.message) {
                    me.render_dashboard(r.message);
                }
            },
            error: function() {
                me.hide_loading();
                frappe.msgprint(__('Error loading dashboard data'));
            }
        });
    }

    render_dashboard(data) {
        this.render_summary_cards(data.summary_cards);
        this.render_funnel_chart(data.flow_funnel);
        this.render_trend_chart(data.daily_trend);
        this.render_bales_stats(data.bales_stats);
        this.render_batch_stats(data.batch_consumption);
        this.render_ro_stats(data.release_order_stats);
        this.render_top_customers(data.top_customers);
        this.render_pending_documents(data.pending_documents);
    }

    render_summary_cards(data) {
        // Quotation
        this.animate_number('#quotation-count', data.quotation.count);
        this.$wrapper.find('#quotation-value').text(this.format_currency(data.quotation.value));
        this.$wrapper.find('#quotation-open').text(data.quotation.open);
        this.$wrapper.find('#quotation-ordered').text(data.quotation.ordered);

        // Sales Order
        this.animate_number('#so-count', data.sales_order.count);
        this.$wrapper.find('#so-value').text(this.format_currency(data.sales_order.value));
        this.$wrapper.find('#so-pending').text(data.sales_order.pending_delivery);
        this.$wrapper.find('#so-qty').text(this.format_number(data.sales_order.qty));

        // Release Order
        this.animate_number('#ro-count', data.release_order.count);
        this.$wrapper.find('#ro-qty').text(this.format_number(data.release_order.qty) + ' Qty Released');
        this.$wrapper.find('#ro-draft').text(data.release_order.draft);
        this.$wrapper.find('#ro-submitted').text(data.release_order.submitted);

        // Delivery Note
        this.animate_number('#dn-count', data.delivery_note.count);
        this.$wrapper.find('#dn-value').text(this.format_currency(data.delivery_note.value));
        this.$wrapper.find('#dn-qty').text(this.format_number(data.delivery_note.qty));
    }

    render_funnel_chart(data) {
        const container = this.$wrapper.find('#funnel-chart');
        container.empty();

        if (!data || data.length === 0) {
            container.html('<div class="empty-state">No data available</div>');
            return;
        }

        const maxCount = Math.max(...data.map(d => d.count));

        data.forEach((item, index) => {
            const width = maxCount > 0 ? Math.max((item.count / maxCount) * 100, 10) : 10;
            const html = `
                <div class="funnel-item fade-in fade-in-delay-${index + 1}">
                    <span class="funnel-label">${item.stage}</span>
                    <div class="funnel-bar-container">
                        <div class="funnel-bar" style="width: ${width}%; background: ${item.color};">
                            ${this.format_number(item.count)}
                        </div>
                    </div>
                </div>
            `;
            container.append(html);
        });
    }

    render_trend_chart(data) {
        const container = this.$wrapper.find('#trend-chart');

        // Prepare datasets
        const dates = new Set();
        data.sales_orders.forEach(d => dates.add(d.date));
        data.delivery_notes.forEach(d => dates.add(d.date));
        data.release_orders.forEach(d => dates.add(d.date));

        const sortedDates = Array.from(dates).sort();

        // Create data maps
        const soMap = {};
        data.sales_orders.forEach(d => soMap[d.date] = d.count);

        const dnMap = {};
        data.delivery_notes.forEach(d => dnMap[d.date] = d.count);

        const roMap = {};
        data.release_orders.forEach(d => roMap[d.date] = d.count);

        // Prepare chart data
        const chartData = {
            labels: sortedDates.map(d => frappe.datetime.str_to_user(d)),
            datasets: [
                {
                    name: 'Sales Orders',
                    values: sortedDates.map(d => soMap[d] || 0)
                },
                {
                    name: 'Release Orders',
                    values: sortedDates.map(d => roMap[d] || 0)
                },
                {
                    name: 'Delivery Notes',
                    values: sortedDates.map(d => dnMap[d] || 0)
                }
            ]
        };

        if (sortedDates.length === 0) {
            container.html('<div class="empty-state">No trend data available</div>');
            return;
        }

        new frappe.Chart(container[0], {
            data: chartData,
            type: 'line',
            height: 280,
            colors: ['#2563EB', '#0891B2', '#059669'],
            lineOptions: {
                regionFill: 1,
                hideDots: 0
            },
            axisOptions: {
                xAxisMode: 'tick',
                xIsSeries: true
            },
            tooltipOptions: {
                formatTooltipX: d => d,
                formatTooltipY: d => d
            }
        });
    }

    render_bales_stats(data) {
        // Status counts
        let packedImport = 0, packedInhouse = 0, dispatched = 0;

        data.by_status.forEach(item => {
            if (item.status === 'Packed Import') packedImport = item.count;
            else if (item.status === 'Packed In House') packedInhouse = item.count;
            else if (item.status === 'Dispatched') dispatched = item.count;
        });

        this.$wrapper.find('#bales-packed-import').text(this.format_number(packedImport));
        this.$wrapper.find('#bales-packed-inhouse').text(this.format_number(packedInhouse));
        this.$wrapper.find('#bales-dispatched').text(this.format_number(dispatched));
        this.$wrapper.find('#bales-period-dispatched').text(this.format_number(data.dispatched_in_period.count || 0));

        // Source chart
        const sourceContainer = this.$wrapper.find('#bales-source-chart');
        if (data.by_source && data.by_source.length > 0) {
            new frappe.Chart(sourceContainer[0], {
                data: {
                    labels: data.by_source.map(d => d.source || 'Unknown'),
                    datasets: [{
                        values: data.by_source.map(d => d.count)
                    }]
                },
                type: 'donut',
                height: 180,
                colors: ['#6366F1', '#8B5CF6', '#06B6D4', '#10B981']
            });
        } else {
            sourceContainer.html('<div class="empty-state">No source data</div>');
        }
    }

    render_batch_stats(data) {
        // Summary
        this.$wrapper.find('#batch-bundles').text(this.format_number(data.summary.total_bundles || 0));
        this.$wrapper.find('#batch-qty').text(this.format_number(Math.abs(data.summary.total_qty || 0)));
        this.$wrapper.find('#batch-dns').text(this.format_number(data.summary.unique_dns || 0));

        // Top items
        const container = this.$wrapper.find('#top-items-container');
        container.empty();

        if (!data.top_items || data.top_items.length === 0) {
            container.html('<div class="empty-state">No items data</div>');
            return;
        }

        data.top_items.forEach((item, index) => {
            const html = `
                <div class="top-item">
                    <div class="top-item-rank">${index + 1}</div>
                    <div class="top-item-info">
                        <div class="top-item-name">${frappe.utils.escape_html(item.item_name || item.item_code)}</div>
                        <div class="top-item-code">${frappe.utils.escape_html(item.item_code)}</div>
                    </div>
                    <div class="top-item-value">${this.format_number(item.total_consumed)}</div>
                </div>
            `;
            container.append(html);
        });
    }

    render_ro_stats(data) {
        // Status chart
        const chartContainer = this.$wrapper.find('#ro-status-chart');
        if (data.by_status && data.by_status.length > 0) {
            new frappe.Chart(chartContainer[0], {
                data: {
                    labels: data.by_status.map(d => d.status),
                    datasets: [{
                        values: data.by_status.map(d => d.count)
                    }]
                },
                type: 'bar',
                height: 150,
                colors: ['#94A3B8', '#6366F1', '#EF4444']
            });
        } else {
            chartContainer.html('<div class="empty-state">No RO data</div>');
        }

        // Conversion stats
        this.$wrapper.find('#ro-total').text(data.conversion.total_ro || 0);
        this.$wrapper.find('#ro-dn-created').text(data.conversion.dn_created || 0);

        // Recent ROs
        const container = this.$wrapper.find('#recent-ros-container');
        container.empty();

        if (!data.recent || data.recent.length === 0) {
            container.html('<div class="empty-state">No recent release orders</div>');
            return;
        }

        data.recent.forEach(ro => {
            const statusClass = ro.docstatus === 1 ? 'success' : 'draft';
            const html = `
                <div class="recent-item" data-doctype="Release Order" data-name="${ro.name}">
                    <div class="recent-item-info">
                        <div class="recent-item-name">${ro.name}</div>
                        <div class="recent-item-sub">${frappe.utils.escape_html(ro.customer_name || '')}</div>
                    </div>
                    <div class="recent-item-meta">
                        <div class="recent-item-value">${this.format_number(ro.total_qty)} Qty</div>
                        <div class="recent-item-date">${frappe.datetime.str_to_user(ro.posting_date)}</div>
                    </div>
                </div>
            `;
            container.append(html);
        });
    }

    render_top_customers(data) {
        const container = this.$wrapper.find('#top-customers-container');
        container.empty();

        if (!data || data.length === 0) {
            container.html('<div class="empty-state">No customer data available</div>');
            return;
        }

        data.forEach((customer, index) => {
            let rankClass = 'default';
            if (index === 0) rankClass = 'gold';
            else if (index === 1) rankClass = 'silver';
            else if (index === 2) rankClass = 'bronze';

            const html = `
                <div class="customer-item" data-customer="${customer.customer}">
                    <div class="customer-rank ${rankClass}">${index + 1}</div>
                    <div class="customer-info">
                        <div class="customer-name">${frappe.utils.escape_html(customer.customer_name || customer.customer)}</div>
                        <div class="customer-code">${frappe.utils.escape_html(customer.customer)}</div>
                    </div>
                    <div class="customer-stats">
                        <div class="customer-value">${this.format_currency(customer.total_value)}</div>
                        <div class="customer-orders">${customer.order_count} orders</div>
                    </div>
                </div>
            `;
            container.append(html);
        });
    }

    render_pending_documents(data) {
        // Pending Quotations
        this.render_pending_list(
            '#pending-quotations',
            '#pending-quotation-count',
            data.quotations,
            'Quotation',
            (item) => `
                <div class="pending-item-header">
                    <span class="pending-item-name">${item.name}</span>
                    <span class="pending-item-value">${this.format_currency(item.grand_total)}</span>
                </div>
                <div class="pending-item-sub">${frappe.utils.escape_html(item.customer_name || '')}</div>
            `
        );

        // Pending Sales Orders
        this.render_pending_list(
            '#pending-sos',
            '#pending-so-count',
            data.sales_orders,
            'Sales Order',
            (item) => `
                <div class="pending-item-header">
                    <span class="pending-item-name">${item.name}</span>
                    <span class="pending-item-value">${this.format_number(item.total_qty)} Qty</span>
                </div>
                <div class="pending-item-sub">${frappe.utils.escape_html(item.customer_name || '')} | ${frappe.datetime.str_to_user(item.transaction_date)}</div>
            `
        );

        // Draft Release Orders
        this.render_pending_list(
            '#pending-ros',
            '#pending-ro-count',
            data.release_orders,
            'Release Order',
            (item) => `
                <div class="pending-item-header">
                    <span class="pending-item-name">${item.name}</span>
                    <span class="pending-item-value">${this.format_number(item.total_qty)} Qty</span>
                </div>
                <div class="pending-item-sub">${frappe.utils.escape_html(item.customer_name || '')} | SO: ${item.sales_order || '-'}</div>
            `
        );

        // Draft Delivery Notes
        this.render_pending_list(
            '#pending-dns',
            '#pending-dn-count',
            data.delivery_notes,
            'Delivery Note',
            (item) => `
                <div class="pending-item-header">
                    <span class="pending-item-name">${item.name}</span>
                    <span class="pending-item-value">${this.format_number(item.total_qty)} Qty</span>
                </div>
                <div class="pending-item-sub">${frappe.utils.escape_html(item.customer_name || '')}</div>
            `
        );
    }

    render_pending_list(containerSelector, countSelector, items, doctype, templateFn) {
        const container = this.$wrapper.find(containerSelector);
        const countEl = this.$wrapper.find(countSelector);

        container.empty();
        countEl.text(items ? items.length : 0);

        if (!items || items.length === 0) {
            container.html('<div class="empty-state">No pending items</div>');
            return;
        }

        items.forEach(item => {
            const html = `
                <div class="pending-item" data-doctype="${doctype}" data-name="${item.name}">
                    ${templateFn(item)}
                </div>
            `;
            container.append(html);
        });
    }

    // Utility functions
    format_currency(value) {
        // Use simple formatting instead of frappe.format() which returns HTML
        const num = parseFloat(value) || 0;
        const formatted = num.toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        // Get currency symbol from system settings
        const symbol = frappe.boot.sysdefaults.currency || '₹';
        return symbol + ' ' + formatted;
    }

    format_number(value) {
        return (value || 0).toLocaleString('en-IN');
    }

    animate_number(selector, value) {
        const el = this.$wrapper.find(selector);
        const duration = 500;
        const start = 0;
        const increment = value / (duration / 16);
        let current = start;

        const animate = () => {
            current += increment;
            if (current < value) {
                el.text(Math.floor(current).toLocaleString('en-IN'));
                requestAnimationFrame(animate);
            } else {
                el.text(value.toLocaleString('en-IN'));
            }
        };

        if (value > 0) {
            animate();
        } else {
            el.text('0');
        }
    }
}
