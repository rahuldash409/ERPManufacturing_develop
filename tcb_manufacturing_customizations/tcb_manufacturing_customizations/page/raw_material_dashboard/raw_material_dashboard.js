frappe.pages['raw-material-dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Raw Material Dashboard',
		single_column: true
	});

	new RawMaterialDashboard(page);
};

class RawMaterialDashboard {
	constructor(page) {
		this.page = page;
		this.page_length = 20;
		this.limit_start = 0;
		this.charts = {};
		this.show_out_of_stock_only = false;  // Filter toggle state
		this.make_form();
	}

	make_form() {
		this.form = new frappe.ui.FieldGroup({
			fields: [
				{
					label: __('Item Code'),
					fieldname: 'item_code',
					fieldtype: 'Link',
					options: 'Item',
					get_query: () => {
						return {
							query: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.page.raw_material_dashboard.raw_material_dashboard.get_raw_material_items'
						};
					},
					change: () => {
						this.limit_start = 0;
						this.refresh();
					}
				},
				{
					fieldtype: 'Column Break'
				},
				{
					label: __('Item Name'),
					fieldname: 'item_name',
					fieldtype: 'Data',
					change: () => {
						this.limit_start = 0;
						this.refresh();
					}
				},
				{
					fieldtype: 'Column Break'
				},
				{
					label: __('Item Group'),
					fieldname: 'item_group',
					fieldtype: 'Link',
					options: 'Item Group',
					change: () => {
						this.limit_start = 0;
						this.refresh();
					}
				},
				{
					fieldtype: 'Column Break'
				},
				{
					label: __('Warehouse'),
					fieldname: 'warehouse',
					fieldtype: 'Link',
					options: 'Warehouse',
					get_query: () => {
						return {
							filters: [
								['warehouse_name', 'not like', '%Segregation%'],
								['warehouse_name', 'not like', '%Finished Goods%']
							]
						};
					},
					change: () => {
						this.limit_start = 0;
						this.refresh();
					}
				},
				{
					fieldtype: 'Column Break'
				},
				{
					label: __('Posting Date'),
					fieldname: 'posting_date',
					fieldtype: 'Date',
					default: frappe.datetime.get_today(),
					change: () => {
						this.limit_start = 0;
						this.refresh();
					}
				},
				{
					fieldtype: 'Section Break'
				},
				{
					fieldtype: 'HTML',
					fieldname: 'report_html'
				},
				{
					fieldtype: 'Section Break'
				},
				{
					fieldtype: 'HTML',
					fieldname: 'dashboard_html'
				}
			],
			body: this.page.body
		});
		this.form.make();

		this.page.add_button(__('Refresh'), () => {
			this.limit_start = 0;
			this.refresh();
		}, { icon: 'refresh' });

		// Add Out of Stock filter button
		this.out_of_stock_btn = this.page.add_button(__('Out Of Stock'), () => {
			this.show_out_of_stock_only = !this.show_out_of_stock_only;
			this.update_filter_button();
			this.limit_start = 0;
			this.refresh();
		}, { icon: 'filter' });

		// Add Export to Excel in Menu
		this.page.add_menu_item(__('Export to Excel'), () => {
			this.export_to_excel();
		}, true);

		this.refresh();
	}

	update_filter_button() {
		// Update button appearance based on filter state
		if (this.show_out_of_stock_only) {
			this.out_of_stock_btn.removeClass('btn-default').addClass('btn-primary');
			this.out_of_stock_btn.find('.btn-label').html(__('Out Of Stock: ON'));
		} else {
			this.out_of_stock_btn.removeClass('btn-primary').addClass('btn-default');
			this.out_of_stock_btn.find('.btn-label').html(__('Out Of Stock'));
		}
	}

	export_to_excel() {
		let item_code = this.form.get_value('item_code');
		let item_name = this.form.get_value('item_name');
		let item_group = this.form.get_value('item_group');
		let warehouse = this.form.get_value('warehouse');
		let posting_date = this.form.get_value('posting_date');

		frappe.call({
			method: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.page.raw_material_dashboard.raw_material_dashboard.export_to_excel',
			args: {
				item_code: item_code,
				item_name: item_name,
				item_group: item_group,
				warehouse: warehouse,
				posting_date: posting_date
			},
			callback: (r) => {
				if (r.message && r.message.file_url) {
					window.open(r.message.file_url);
				}
			}
		});
	}

	refresh() {
		let item_code = this.form.get_value('item_code');
		let item_name = this.form.get_value('item_name');
		let item_group = this.form.get_value('item_group');
		let warehouse = this.form.get_value('warehouse');
		let posting_date = this.form.get_value('posting_date');

		// Show loading state
		this.form.get_field('dashboard_html').html(`
			<div class="text-center text-muted" style="padding: 40px 0;">
				<i class="fa fa-spinner fa-spin fa-2x"></i>
				<p class="mt-2">${__('Loading Dashboard...')}</p>
			</div>
		`);

		this.form.get_field('report_html').html(`
			<div class="text-center text-muted" style="padding: 40px 0;">
				<i class="fa fa-spinner fa-spin fa-2x"></i>
				<p class="mt-2">${__('Loading...')}</p>
			</div>
		`);

		// Fetch dashboard stats
		frappe.call({
			method: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.page.raw_material_dashboard.raw_material_dashboard.get_dashboard_stats',
			args: {
				warehouse: warehouse,
				posting_date: posting_date
			},
			callback: (r) => {
				if (r.message) {
					this.render_dashboard(r.message);
				}
			}
		});

		// Fetch table data
		frappe.call({
			method: 'tcb_manufacturing_customizations.tcb_manufacturing_customizations.page.raw_material_dashboard.raw_material_dashboard.get_raw_materials',
			args: {
				item_code: item_code,
				item_name: item_name,
				item_group: item_group,
				warehouse: warehouse,
				posting_date: posting_date,
				limit_start: this.limit_start,
				limit_page_length: this.page_length,
				out_of_stock_only: this.show_out_of_stock_only ? 1 : 0
			},
			callback: (r) => {
				if (r.message) {
					this.render(r.message.data, r.message.total_count);
				}
			}
		});
	}

	render_dashboard(data) {
		// Destroy existing charts before re-rendering
		this.destroy_charts();

		let html = `
			<style>
				.rmd-dashboard {
					--rmd-blue: var(--blue-500, #2490EF);
					--rmd-green: var(--green-500, #29CD42);
					--rmd-red: var(--red-500, #E24C4C);
					--rmd-purple: var(--purple-500, #7B69EE);
					--rmd-orange: var(--orange-500, #FE8F40);
					--rmd-cyan: var(--cyan-500, #00BCD4);
				}
				.rmd-summary-cards {
					display: grid;
					grid-template-columns: repeat(3, 1fr);
					gap: var(--padding-md);
					margin-bottom: var(--padding-lg);
				}
				@media (max-width: 768px) {
					.rmd-summary-cards {
						grid-template-columns: 1fr;
					}
				}
				.rmd-card {
					background: var(--card-bg);
					border-radius: var(--border-radius-lg);
					padding: var(--padding-lg);
					border: 1px solid var(--border-color);
					transition: all 0.2s ease;
					position: relative;
					overflow: hidden;
				}
				.rmd-card:hover {
					box-shadow: var(--shadow-md);
				}
				.rmd-card::before {
					content: '';
					position: absolute;
					left: 0;
					top: 0;
					bottom: 0;
					width: 4px;
				}
				.rmd-card.blue::before { background: var(--rmd-blue); }
				.rmd-card.green::before { background: var(--rmd-green); }
				.rmd-card.red::before { background: var(--rmd-red); }
				.rmd-card.purple::before { background: var(--rmd-purple); }
				.rmd-card-header {
					display: flex;
					align-items: center;
					gap: var(--padding-sm);
					margin-bottom: var(--padding-md);
				}
				.rmd-card-icon {
					width: 40px;
					height: 40px;
					border-radius: var(--border-radius-md);
					display: flex;
					align-items: center;
					justify-content: center;
				}
				.rmd-card-icon svg {
					width: 20px;
					height: 20px;
				}
				.rmd-card.blue .rmd-card-icon { background: var(--blue-50, #E8F5FE); }
				.rmd-card.blue .rmd-card-icon svg { stroke: var(--rmd-blue); }
				.rmd-card.green .rmd-card-icon { background: var(--green-50, #E4F5E9); }
				.rmd-card.green .rmd-card-icon svg { stroke: var(--rmd-green); }
				.rmd-card.red .rmd-card-icon { background: var(--red-50, #FCEAEA); }
				.rmd-card.red .rmd-card-icon svg { stroke: var(--rmd-red); }
				.rmd-card.purple .rmd-card-icon { background: var(--purple-50, #F0EEFE); }
				.rmd-card.purple .rmd-card-icon svg { stroke: var(--rmd-purple); }
				.rmd-card-label {
					font-size: var(--text-sm);
					color: var(--text-muted);
					font-weight: 500;
				}
				.rmd-card-value {
					font-size: var(--text-3xl);
					font-weight: 700;
					color: var(--text-color);
					line-height: 1.2;
				}
				.rmd-charts-row {
					display: grid;
					grid-template-columns: 1fr 1fr;
					gap: var(--padding-lg);
					margin-bottom: var(--padding-lg);
				}
				@media (max-width: 768px) {
					.rmd-charts-row {
						grid-template-columns: 1fr;
					}
				}
				.rmd-chart-card {
					background: var(--card-bg);
					border-radius: var(--border-radius-lg);
					/* padding: var(--padding-lg); */
					padding: 10px !important;
					border: 1px solid var(--border-color);
				}
				.rmd-chart-title {
					font-size: var(--text-base);
					font-weight: 600;
					color: var(--heading-color);
					margin-bottom: var(--padding-md);
					display: flex !important;
					align-items: center !important;
					justify-content: flex-start !important;
					gap: 8px;
				}
				.rmd-chart-title svg.icon {
					width: 18px;
					height: 18px;
					flex-shrink: 0;
					display: inline-block;
					margin: 0 !important;
				}
				.rmd-chart-title span {
					display: inline-block;
				}
				.rmd-chart-container {
					min-height: 200px;
				}
				.rmd-trend-card {
					background: var(--card-bg);
					border-radius: var(--border-radius-lg);
					/* padding: var(--padding-lg); */
					padding: 10px !important;
					border: 1px solid var(--border-color);
					margin-bottom: var(--padding-lg);
				}
				.rmd-shortage-list {
					max-height: 200px;
					overflow-y: auto;
				}
				.rmd-shortage-item {
					display: flex;
					justify-content: space-between;
					align-items: center;
					padding: var(--padding-sm) var(--padding-md);
					border-radius: var(--border-radius-md);
					margin-bottom: var(--padding-xs);
					background: var(--fg-color);
					transition: all 0.2s ease;
					cursor: pointer;
				}
				.rmd-shortage-item:hover {
					background: var(--bg-light-gray);
				}
				.rmd-shortage-item .item-info {
					flex: 1;
					min-width: 0;
				}
				.rmd-shortage-item .item-code {
					font-size: var(--text-sm);
					font-weight: 600;
					color: var(--text-color);
					white-space: nowrap;
					overflow: hidden;
					text-overflow: ellipsis;
				}
				.rmd-shortage-item .item-name {
					font-size: var(--text-xs);
					color: var(--text-muted);
					white-space: nowrap;
					overflow: hidden;
					text-overflow: ellipsis;
				}
				.rmd-shortage-item .qty-badge {
					padding: var(--padding-xs) var(--padding-sm);
					border-radius: var(--border-radius-full);
					font-size: var(--text-xs);
					font-weight: 600;
					margin-left: var(--padding-md);
					white-space: nowrap;
				}
				.rmd-shortage-item .qty-badge.negative {
					background: var(--red-50, #FCEAEA);
					color: var(--red-600, #C82124);
				}
				.rmd-shortage-item .qty-badge.positive {
					background: var(--green-50, #E4F5E9);
					color: var(--green-600, #22882A);
				}
			</style>
			<div class="rmd-dashboard">
				<!-- Summary Cards -->
				<div class="rmd-summary-cards">
					<div class="rmd-card blue">
						<div class="rmd-card-header">
							<div class="rmd-card-icon">
								<svg class="icon"><use href="#icon-stock"></use></svg>
							</div>
							<div class="rmd-card-label">${__('Total Items')}</div>
						</div>
						<div class="rmd-card-value">${this.format_number(data.summary.total_items)}</div>
					</div>
					<div class="rmd-card green">
						<div class="rmd-card-header">
							<div class="rmd-card-icon">
								<svg class="icon"><use href="#icon-tick"></use></svg>
							</div>
							<div class="rmd-card-label">${__('In Stock')}</div>
						</div>
						<div class="rmd-card-value">${this.format_number(data.summary.in_stock)}</div>
					</div>
					<div class="rmd-card red">
						<div class="rmd-card-header">
							<div class="rmd-card-icon">
								<svg class="icon"><use href="#icon-restriction"></use></svg>
							</div>
							<div class="rmd-card-label">${__('Out of Stock')}</div>
						</div>
						<div class="rmd-card-value">${this.format_number(data.summary.out_of_stock)}</div>
					</div>
				</div>

				<!-- Charts Row -->
				<div class="rmd-charts-row">
					<!-- Pie Chart -->
					<div class="rmd-chart-card">
						<div class="rmd-chart-title" style="display: flex; align-items: center; justify-content: flex-start; gap: 8px;">
							<svg class="icon icon-sm" style="flex-shrink: 0; margin: 0;"><use href="#icon-chart"></use></svg>
							<span>${__('Stock Status')}</span>
						</div>
						<div class="rmd-chart-container" id="rmd-pie-chart"></div>
					</div>

					<!-- Shortage List -->
					<div class="rmd-chart-card">
						<div class="rmd-chart-title" style="display: flex; align-items: center; justify-content: flex-start; gap: 8px;">
							<svg class="icon icon-sm" style="flex-shrink: 0; margin: 0;"><use href="#icon-sort-descending"></use></svg>
							<span>${__('Top 10 Shortage Items')}</span>
						</div>
						<div class="rmd-shortage-list" id="rmd-shortage-list">
							${this.render_shortage_list(data.top_shortage)}
						</div>
					</div>
				</div>

				<!-- Trend Chart -->
				<div class="rmd-trend-card">
					<div class="rmd-chart-title" style="display: flex; align-items: center; justify-content: flex-start; gap: 8px;">
						<svg class="icon icon-sm" style="flex-shrink: 0; margin: 0;"><use href="#icon-gantt"></use></svg>
						<span>${__('Stock Trend (Last 7 Days)')}</span>
					</div>
					<div class="rmd-chart-container" id="rmd-trend-chart"></div>
				</div>
			</div>
		`;

		this.form.get_field('dashboard_html').html(html);

		// Render charts after DOM is ready
		setTimeout(() => {
			this.render_pie_chart(data.stock_status);
			this.render_trend_chart(data.trend_data);
		}, 100);
	}

	render_shortage_list(items) {
		if (!items || items.length === 0) {
			return `<div class="text-center text-muted py-4">${__('No shortage items')}</div>`;
		}

		return items.map(item => {
			let badge_class = item.available_qty < 0 ? 'negative' : 'positive';
			return `
				<div class="rmd-shortage-item">
					<div class="item-info">
						<div class="item-code">${item.item_code}</div>
						<div class="item-name">${item.item_name || ''}</div>
					</div>
					<div class="qty-badge ${badge_class}">${frappe.format(item.available_qty, {fieldtype: 'Float'})}</div>
				</div>
			`;
		}).join('');
	}

	destroy_charts() {
		// Properly destroy chart instances before re-rendering
		if (this.charts.pie) {
			try {
				this.charts.pie.destroy();
			} catch (e) {
				// Ignore errors during destroy
			}
			this.charts.pie = null;
		}
		if (this.charts.trend) {
			try {
				this.charts.trend.destroy();
			} catch (e) {
				// Ignore errors during destroy
			}
			this.charts.trend = null;
		}
	}

	render_pie_chart(stock_status) {
		const container = document.getElementById('rmd-pie-chart');
		if (!container) return;

		const in_stock = stock_status.find(s => s.status === 'In Stock')?.count || 0;
		const out_of_stock = stock_status.find(s => s.status === 'Out of Stock')?.count || 0;

		if (in_stock === 0 && out_of_stock === 0) {
			container.innerHTML = `<div class="text-center text-muted py-4">${__('No data available')}</div>`;
			return;
		}

		this.charts.pie = new frappe.Chart(container, {
			data: {
				labels: [__('In Stock'), __('Out of Stock')],
				datasets: [{
					values: [in_stock, out_of_stock]
				}]
			},
			type: 'donut',
			height: 200,
			colors: ['green', 'red']
		});
	}

	render_trend_chart(trend_data) {
		const container = document.getElementById('rmd-trend-chart');
		if (!container) return;

		if (!trend_data || trend_data.length === 0) {
			container.innerHTML = `<div class="text-center text-muted py-4">${__('No trend data available')}</div>`;
			return;
		}

		const labels = trend_data.map(d => frappe.datetime.str_to_user(d.date));
		const actual_qty = trend_data.map(d => d.actual_qty);
		const po_qty = trend_data.map(d => d.po_qty);
		const wo_remaining = trend_data.map(d => d.wo_remaining);

		this.charts.trend = new frappe.Chart(container, {
			data: {
				labels: labels,
				datasets: [
					{
						name: __('Actual Qty'),
						values: actual_qty
					},
					{
						name: __('PO Qty'),
						values: po_qty
					},
					{
						name: __('WO Remaining'),
						values: wo_remaining
					}
				]
			},
			type: 'line',
			height: 250,
			colors: ['blue', 'green', 'orange'],
			lineOptions: {
				regionFill: 1,
				hideDots: 0
			},
			axisOptions: {
				xAxisMode: 'tick',
				xIsSeries: true
			},
			tooltipOptions: {
				formatTooltipY: d => frappe.format(d, {fieldtype: 'Float'})
			}
		});
	}

	format_number(num) {
		if (num >= 1000000) {
			return (num / 1000000).toFixed(1) + 'M';
		} else if (num >= 1000) {
			return (num / 1000).toFixed(1) + 'K';
		}
		return num.toLocaleString();
	}

	get_row_color(available_qty) {
		if (available_qty <= 0) {
			return 'danger';  // Red - Out of stock
		} else {
			return 'success';  // Green - In stock
		}
	}

	render(data, total_count) {
		// Store total_count for pagination events
		this.total_count = total_count;

		if (!data || data.length === 0) {
			this.form.get_field('report_html').html(`
				<div class="text-center text-muted" style="padding: 40px 0;">
					<i class="fa fa-inbox fa-3x mb-3"></i>
					<p>${__('No raw materials found')}</p>
				</div>
			`);
			return;
		}

		let rows = data.map((row, index) => {
			let color_class = this.get_row_color(row.available_qty);
			let sr_no = this.limit_start + index + 1;
			return `
				<tr class="indicator-${color_class}">
					<td class="sr-cell">${sr_no}</td>
					<td class="item-cell">
						<a href="/app/item/${row.item_code}" class="item-code">${row.item_code}</a>
						<div class="item-name">${row.item_name || ''}</div>
					</td>
					<td class="item-group-cell">${row.item_group || ''}</td>
					<td class="warehouse-cell"><a href="/app/warehouse/${row.warehouse}">${row.warehouse || ''}</a></td>
					<td class="description-cell">${row.description || ''}</td>
					<td class="uom-cell">${row.uom || ''}</td>
					<td class="text-right">${frappe.format(row.actual_qty || 0, {fieldtype: 'Float'})}</td>
					<td class="text-right">${frappe.format(row.po_qty || 0, {fieldtype: 'Float'})}</td>
					<td class="text-right">${frappe.format(row.wo_remaining_qty || 0, {fieldtype: 'Float'})}</td>
					<td class="text-right font-weight-bold">${frappe.format(row.available_qty || 0, {fieldtype: 'Float'})}</td>
				</tr>
			`;
		}).join('');

		let html = `
			<style>
				.raw-material-section {
					border: 1px solid var(--border-color);
					border-radius: var(--border-radius-lg);
					background: var(--card-bg);
					margin-bottom: 15px;
					box-shadow: var(--shadow-sm);
				}
				.raw-material-section .section-header {
					display: flex;
					justify-content: space-between;
					align-items: center;
					padding: 12px 16px;
					border-bottom: 1px solid var(--border-color);
					background: linear-gradient(135deg, var(--bg-light-gray) 0%, var(--card-bg) 100%);
					border-radius: var(--border-radius-lg) var(--border-radius-lg) 0 0;
				}
				.raw-material-section .section-title {
					font-weight: 600;
					font-size: 14px;
					margin: 0;
					color: var(--heading-color);
					display: flex;
					align-items: center;
					gap: 8px;
				}
				.raw-material-section .section-body {
					padding: 0;
				}
				.raw-material-dashboard .legend-wrapper {
					display: flex;
					align-items: center;
					gap: 12px;
				}
				.raw-material-dashboard .legend-item {
					display: inline-flex;
					align-items: center;
					font-size: 11px;
					color: var(--text-muted);
				}
				.raw-material-dashboard .legend-box {
					display: inline-block;
					width: 14px;
					height: 14px;
					margin-right: 6px;
					border-radius: var(--border-radius-sm);
					border: 1px solid var(--border-color);
				}
				.raw-material-dashboard .report-table {
					font-size: 12px;
					margin-bottom: 0;
					width: 100%;
					table-layout: fixed;
					border-collapse: separate;
					border-spacing: 0;
				}
				.raw-material-dashboard .report-table thead {
					position: sticky;
					top: 0;
					z-index: 1;
				}
				.raw-material-dashboard .report-table th {
					white-space: nowrap;
					font-weight: 600;
					padding: 10px 12px;
					font-size: 11px;
					text-transform: uppercase;
					letter-spacing: 0.5px;
					color: var(--text-muted);
					background: var(--bg-light-gray);
					border-bottom: 2px solid var(--border-color);
				}
				.raw-material-dashboard .report-table tbody tr {
					transition: all 0.15s ease;
				}
				.raw-material-dashboard .report-table tbody tr:hover {
					transform: scale(1.002);
					box-shadow: 0 2px 8px rgba(0,0,0,0.08);
					position: relative;
					z-index: 1;
				}
				.raw-material-dashboard .report-table td {
					vertical-align: middle;
					padding: 6px 4px;
					height: 44px;
					max-height: 44px;
					overflow: hidden;
					text-overflow: ellipsis;
					white-space: nowrap;
					border-bottom: 1px solid var(--border-color);
				}
				.raw-material-dashboard .report-table tbody tr:last-child td {
					border-bottom: none;
				}
				.raw-material-dashboard .indicator-danger {
					background: linear-gradient(90deg, var(--bg-red) 0%, rgba(255,199,206,0.3) 100%) !important;
					border-left: 3px solid var(--red-500) !important;
				}
				.raw-material-dashboard .indicator-success {
					background: linear-gradient(90deg, var(--bg-green) 0%, rgba(198,239,206,0.3) 100%) !important;
					border-left: 3px solid var(--green-500) !important;
				}
				.raw-material-dashboard .report-table td.item-cell {
					white-space: normal;
					line-height: 1.3;
				}
				.raw-material-dashboard .report-table td.item-cell .item-code {
					font-size: 12px;
					font-weight: 600;
					display: block;
					color: var(--primary);
				}
				.raw-material-dashboard .report-table td.item-cell .item-code:hover {
					text-decoration: underline;
				}
				.raw-material-dashboard .report-table td.item-cell .item-name {
					font-size: 10px;
					font-weight: normal;
					color: var(--text-neutral);
					overflow: hidden;
					text-overflow: ellipsis;
					white-space: nowrap;
					margin-top: 2px;
				}
				.raw-material-dashboard .report-table td.item-group-cell {
					font-size: 11px;
					color: var(--text-muted);
				}
				.raw-material-dashboard .report-table td.warehouse-cell a {
					font-size: 11px;
					color: var(--text-neutral);
				}
				.raw-material-dashboard .report-table td.warehouse-cell a:hover {
					color: var(--primary);
				}
				.raw-material-dashboard .report-table td.description-cell {
					font-size: 10px;
					color: var(--text-neutral);
				}
				.raw-material-dashboard .report-table td.text-right {
					font-family: var(--font-stack-monospace, monospace);
					font-size: 11px;
				}
				.raw-material-dashboard .report-table td.text-right.font-weight-bold {
					font-size: 12px;
					color: var(--text-color);
				}
				.raw-material-dashboard .table-responsive {
					width: 100%;
					overflow-x: hidden;
					overflow-y: auto;
					max-height: calc(100vh - 320px);
					min-height: 400px;
					scrollbar-width: thin;
					scrollbar-color: var(--gray-300) transparent;
				}
				.raw-material-dashboard .table-responsive::-webkit-scrollbar {
					width: 8px;
				}
				.raw-material-dashboard .table-responsive::-webkit-scrollbar-track {
					background: transparent;
				}
				.raw-material-dashboard .table-responsive::-webkit-scrollbar-thumb {
					background-color: var(--gray-300);
					border-radius: 4px;
				}
				.raw-material-dashboard .table-responsive::-webkit-scrollbar-thumb:hover {
					background-color: var(--gray-400);
				}
				.raw-material-dashboard .table-responsive::-webkit-scrollbar-thumb:active {
					background-color: var(--gray-500);
				}
				.raw-material-dashboard .sr-cell {
					text-align: center;
					color: var(--text-neutral);
					font-size: 10px;
					font-weight: 600;
				}
				.raw-material-dashboard .report-table td.uom-cell {
					font-size: 11px;
					color: var(--text-neutral);
					text-align: center;
				}
			</style>
			<div class="raw-material-section">
				<div class="section-header">
					<h6 class="section-title">${__('Raw Material Stock')}</h6>
					<div class="legend-wrapper">
						<span class="legend-item">
							<span class="legend-box p-2 border border shadow-sm rounded" style="background-color: var(--bg-green);">${__('> 0')} (Available)</span>
						</span>
						<span class="legend-item">
							<span class="legend-box p-2 border border shadow-sm rounded" style="background-color: var(--bg-red);">${__('≤ 0')} (Out of Stock)</span>
						</span>
					</div>
				</div>
				<div class="section-body" style="padding: 5px !important;">
					<div class="raw-material-dashboard">
						<div class="table-responsive">
							<table class="table table-bordered report-table mt-0">
								<thead style="background: var(--bg-light-gray);">
									<tr>
										<th class="text-center" style="width: 50px;">${__('Sr.')}</th>
										<th style="width: 220px;">${__('Item')}</th>
										<th style="width: 140px;">${__('Item Group')}</th>
										<th style="width: 140px;">${__('Warehouse')}</th>
										<th>${__('Description')}</th>
										<th style="width: 60px;">${__('UOM')}</th>
										<th class="text-right text-primary" style="width: 100px;">${__('Actual Qty')}</th>
										<th class="text-right text-primary" style="width: 80px;">${__('PO Qty')}</th>
										<th class="text-right text-primary" style="width: 100px;">${__('WO Rem Qty')}</th>
										<th class="text-right text-primary" style="width: 120px;">${__('Available Qty')}</th>
									</tr>
								</thead>
								<tbody>
									${rows}
								</tbody>
							</table>
						</div>
						${this.get_pagination_html(total_count)}
					</div>
				</div>
			</div>
		`;

		this.form.get_field('report_html').html(html);
		this.setup_pagination_events();
	}

	get_pagination_html(total_count) {
		let total_pages = Math.ceil(total_count / this.page_length);
		let current_page = Math.floor(this.limit_start / this.page_length) + 1;
		let start_record = this.limit_start + 1;
		let end_record = Math.min(this.limit_start + this.page_length, total_count);

		// Page size options
		let page_sizes = [20, 50, 100, 200];
		let page_size_options = page_sizes.map(size =>
			`<option value="${size}" ${this.page_length === size ? 'selected' : ''}>${size}</option>`
		).join('');

		// Generate page number buttons (show max 5 pages around current)
		let page_buttons = '';
		if (total_pages > 1) {
			let start_page = Math.max(1, current_page - 2);
			let end_page = Math.min(total_pages, start_page + 4);

			// Adjust start if we're near the end
			if (end_page - start_page < 4) {
				start_page = Math.max(1, end_page - 4);
			}

			for (let i = start_page; i <= end_page; i++) {
				page_buttons += `
					<button class="btn btn-page ${i === current_page ? 'btn-primary' : 'btn-default'}"
						data-page="${i}" ${i === current_page ? 'disabled' : ''}>
						${i}
					</button>
				`;
			}
		}

		return `
			<style>
				.rmd-pagination {
					display: flex;
					justify-content: space-between;
					align-items: center;
					padding: 12px 0;
					border-top: 1px solid var(--border-color);
					margin-top: 10px;
					flex-wrap: wrap;
					gap: 10px;
				}
				.rmd-pagination .pagination-info {
					display: flex;
					align-items: center;
					gap: 15px;
					flex-wrap: wrap;
				}
				.rmd-pagination .pagination-info .info-text {
					font-size: 12px;
					color: var(--text-muted);
				}
				.rmd-pagination .page-size-selector {
					display: flex;
					align-items: center;
					gap: 8px;
				}
				.rmd-pagination .page-size-selector label {
					font-size: 12px;
					color: var(--text-muted);
					margin: 0;
				}
				.rmd-pagination .page-size-selector select {
					padding: 4px 8px;
					font-size: 12px;
					border: 1px solid var(--border-color);
					border-radius: var(--border-radius);
					background: var(--card-bg);
					color: var(--text-color);
					cursor: pointer;
				}
				.rmd-pagination .pagination-controls {
					display: flex;
					align-items: center;
					gap: 8px;
				}
				.rmd-pagination .pagination-controls .btn {
					padding: 4px 10px;
					font-size: 12px;
					border: 1px solid var(--border-color);
					background: var(--card-bg);
					color: var(--text-color);
					cursor: pointer;
					transition: all 0.2s;
				}
				.rmd-pagination .pagination-controls .btn:hover:not(:disabled) {
					background: var(--bg-light-gray);
					border-color: var(--primary);
				}
				.rmd-pagination .pagination-controls .btn:disabled {
					opacity: 0.5;
					cursor: not-allowed;
				}
				.rmd-pagination .pagination-controls .btn-primary {
					background: var(--primary);
					border-color: var(--primary);
					color: white;
				}
				.rmd-pagination .pagination-controls .btn-page {
					min-width: 32px;
				}
				.rmd-pagination .page-jump {
					display: flex;
					align-items: center;
					gap: 6px;
				}
				.rmd-pagination .page-jump label {
					font-size: 12px;
					color: var(--text-muted);
					margin: 0;
				}
				.rmd-pagination .page-jump input {
					width: 50px;
					padding: 4px 8px;
					font-size: 12px;
					border: 1px solid var(--border-color);
					border-radius: var(--border-radius);
					background: var(--card-bg);
					color: var(--text-color);
					text-align: center;
				}
				.rmd-pagination .page-jump .btn-go {
					padding: 4px 10px;
					font-size: 12px;
				}
				@media (max-width: 768px) {
					.rmd-pagination {
						flex-direction: column;
						align-items: flex-start;
					}
					.rmd-pagination .pagination-controls {
						width: 100%;
						justify-content: center;
					}
				}
			</style>
			<div class="rmd-pagination">
				<div class="pagination-info">
					<span class="info-text">
						${__('Showing')} <strong>${start_record}</strong> ${__('to')} <strong>${end_record}</strong> ${__('of')} <strong>${total_count}</strong> ${__('items')}
					</span>
					<div class="page-size-selector">
						<label>${__('Per page')}:</label>
						<select class="page-size-select">
							${page_size_options}
						</select>
					</div>
				</div>
				<div class="pagination-controls">
					<button class="btn btn-first" ${current_page === 1 ? 'disabled' : ''} title="${__('First Page')}">
						<i class="fa fa-angle-double-left"></i>
					</button>
					<button class="btn btn-prev" ${current_page === 1 ? 'disabled' : ''} title="${__('Previous Page')}">
						<i class="fa fa-angle-left"></i>
					</button>
					${page_buttons}
					<button class="btn btn-next" ${current_page === total_pages ? 'disabled' : ''} title="${__('Next Page')}">
						<i class="fa fa-angle-right"></i>
					</button>
					<button class="btn btn-last" ${current_page === total_pages ? 'disabled' : ''} title="${__('Last Page')}">
						<i class="fa fa-angle-double-right"></i>
					</button>
					${total_pages > 5 ? `
						<div class="page-jump">
							<label>${__('Go to')}:</label>
							<input type="number" class="page-input" min="1" max="${total_pages}" value="${current_page}">
							<button class="btn btn-go">${__('Go')}</button>
						</div>
					` : ''}
				</div>
			</div>
		`;
	}

	setup_pagination_events() {
		let $wrapper = $(this.form.get_field('report_html').wrapper);
		let total_count = this.total_count || 0;
		let total_pages = Math.ceil(total_count / this.page_length);

		// Page size change
		$wrapper.find('.page-size-select').off('change').on('change', (e) => {
			this.page_length = parseInt(e.target.value);
			this.limit_start = 0;
			this.refresh();
		});

		// First page
		$wrapper.find('.btn-first').off('click').on('click', () => {
			this.limit_start = 0;
			this.refresh();
		});

		// Previous page
		$wrapper.find('.btn-prev').off('click').on('click', () => {
			if (this.limit_start >= this.page_length) {
				this.limit_start -= this.page_length;
				this.refresh();
			}
		});

		// Next page
		$wrapper.find('.btn-next').off('click').on('click', () => {
			this.limit_start += this.page_length;
			this.refresh();
		});

		// Last page
		$wrapper.find('.btn-last').off('click').on('click', () => {
			this.limit_start = (total_pages - 1) * this.page_length;
			this.refresh();
		});

		// Direct page click
		$wrapper.find('.btn-page').off('click').on('click', (e) => {
			let page = parseInt($(e.currentTarget).data('page'));
			this.limit_start = (page - 1) * this.page_length;
			this.refresh();
		});

		// Page jump
		$wrapper.find('.btn-go').off('click').on('click', () => {
			let page = parseInt($wrapper.find('.page-input').val());
			if (page >= 1 && page <= total_pages) {
				this.limit_start = (page - 1) * this.page_length;
				this.refresh();
			}
		});

		// Enter key on page input
		$wrapper.find('.page-input').off('keypress').on('keypress', (e) => {
			if (e.which === 13) {
				$wrapper.find('.btn-go').click();
			}
		});
	}
}
