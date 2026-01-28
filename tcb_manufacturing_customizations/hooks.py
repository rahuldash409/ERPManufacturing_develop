app_name = "tcb_manufacturing_customizations"
app_title = "Tcb Manufacturing Customizations"
app_publisher = "rahul.dash@spplgroup.com"
app_description = "TCB Manufacturing Customizations"
app_email = "rahul.dash@spplgroup.com"
app_license = "mit"

# Apps
# ------------------
override_whitelisted_methods = {
    "erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry": "tcb_manufacturing_customizations.overrides.workorder.make_stock_entry",
    "erpnext.manufacturing.doctype.production_plan.production_plan.get_items_for_material_requests": "tcb_manufacturing_customizations.overrides.production_plan.get_items_for_material_requests_override",
}

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "tcb_manufacturing_customizations",
# 		"logo": "/assets/tcb_manufacturing_customizations/logo.png",
# 		"title": "Tcb Manufacturing Customizations",
# 		"route": "/tcb_manufacturing_customizations",
# 		"has_permission": "tcb_manufacturing_customizations.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = (
    "/assets/tcb_manufacturing_customizations/css/tcb_manufacturing_customizations.css"
)
app_include_js = [
    "/assets/tcb_manufacturing_customizations/js_overrides/stock_entry.js",
    "/assets/tcb_manufacturing_customizations/js_overrides/stock_entry_detail.js",
]

# include js, css files in header of web template
# web_include_css = "/assets/tcb_manufacturing_customizations/css/tcb_manufacturing_customizations.css"
# web_include_js = "/assets/tcb_manufacturing_customizations/js/tcb_manufacturing_customizations.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "tcb_manufacturing_customizations/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Quality Inspection": "public/js/quality_inspection.js",
    "Purchase Order": "public/js/purchase_order.js",
    "Work Order": "public/js/work_order.js",
    "Job Card": "public/js/job_card.js",
    "Purchase Receipt": "public/js/purchase_receipt.js",
    "BOM": "public/js/bom.js",
    "Delivery Estimate": [
        "public/js/delivery_estimate.js",
        "public/js/delivery_estimate_urgent.js",
    ],
    "Freight Master": "public/js/freight_master.js",
    "Workstation": "public/js/workstation.js",
    "Stock Reconciliation": "public/js/stock_reconciliation.js",
    "Batch": "public/js/batch.js",
    "Sales Invoice": "public/js/sales_invoice.js",
    "Get All Batch Qty": "public/js/get_batch_qty.js",
    "Delivery Note": "public/js/delivery_note.js",
    "Item": "public/js/item.js",
    "Production Plan": "public/js/production_plan.js",
    "Sales Order": "public/js/sales_order.js",
    "Asset Repair": "public/js/asset_repair.js",
    "Asset": "public/js/asset.js",
    "Asset Maintenance Log": "public/js/asset_maintenance_log.js",
    "Material Request": "public/js/material_request.js",
}

doctype_list_js = {"Stock Entry": "public/js/stock_entry_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "tcb_manufacturing_customizations/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "tcb_manufacturing_customizations.utils.jinja_methods",
# 	"filters": "tcb_manufacturing_customizations.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "tcb_manufacturing_customizations.install.before_install"
after_install = (
    "tcb_manufacturing_customizations.install.manufacturing_settings.after_install"
)

# Uninstallation
# ------------

# before_uninstall = "tcb_manufacturing_customizations.uninstall.before_uninstall"
# after_uninstall = "tcb_manufacturing_customizations.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "tcb_manufacturing_customizations.utils.before_app_install"
# after_app_install = "tcb_manufacturing_customizations.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "tcb_manufacturing_customizations.utils.before_app_uninstall"
# after_app_uninstall = "tcb_manufacturing_customizations.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "tcb_manufacturing_customizations.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
    "Work Order": "tcb_manufacturing_customizations.overrides.workorder.CustomWorkOrder",
    "Delivery Note": "tcb_manufacturing_customizations.overrides.delivery_note.CustomDeliveryNote",
    "Production Plan": "tcb_manufacturing_customizations.overrides.production_plan.CustomProductionPlan",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Job Card": {
        "validate": [
            "tcb_manufacturing_customizations.doc_events.job_card.validate_jc",
        ],
        "before_submit": [
            "tcb_manufacturing_customizations.doc_events.job_card.checkprodqty",
        ],
        "on_cancel": [
            "tcb_manufacturing_customizations.doc_events.job_card.cancel_jc",
        ],
    },
    "Stock Entry": {
        "before_insert": [
            "tcb_manufacturing_customizations.doc_events.stock_entry.roundqty",
            "tcb_manufacturing_customizations.doc_events.stock_entry.updateexpenses"
        ],
        # "validate":["tcb_manufacturing_customizations.overrides.workorder.validate","tcb_manufacturing_customizations.doc_events.stock_entry.update_batches",
        #             "tcb_manufacturing_customizations.doc_events.stock_entry.set_sub_batch","tcb_manufacturing_customizations.doc_events.stock_entry.split_final_product"],
        "validate": [
            "tcb_manufacturing_customizations.overrides.workorder.validate",
            "tcb_manufacturing_customizations.doc_events.stock_entry.update_batches",
            "tcb_manufacturing_customizations.doc_events.stock_entry.split_final_product",
            "tcb_manufacturing_customizations.doc_events.stock_entry.seperate_repairable_spares_quantities",
            "tcb_manufacturing_customizations.doc_events.stock_entry.roundqty",
        ],
        "on_trash": [
            "tcb_manufacturing_customizations.overrides.workorder.on_trash",
            "tcb_manufacturing_customizations.doc_events.stock_entry.delete_manufacture_bales",
        ],
        "on_submit": [
            # New Manufacturing flow - create bales from Manufacture SE
            "tcb_manufacturing_customizations.doc_events.stock_entry.create_bales_from_manufacture_se",
            # Populate Job Card packaging materials on Material Transfer for Manufacture
            "tcb_manufacturing_customizations.doc_events.stock_entry.populate_packaging_materials_on_transfer",
            "tcb_manufacturing_customizations.doc_events.stock_entry.on_submit_update_maintenance_log_spares_status",
            "tcb_manufacturing_customizations.doc_events.stock_entry.flagJc",
            "tcb_manufacturing_customizations.doc_events.stock_entry.materialreceipt",
        ],
        "on_cancel": [
            "tcb_manufacturing_customizations.overrides.workorder.on_cancel",
            # New Manufacturing flow - cancel bales when Manufacture SE is cancelled
            "tcb_manufacturing_customizations.doc_events.stock_entry.cancel_bales_from_manufacture_se",
            # Clear Job Card packaging materials on cancel
            "tcb_manufacturing_customizations.doc_events.stock_entry.clear_packaging_materials_on_cancel",
            "tcb_manufacturing_customizations.doc_events.stock_entry.on_cancel_update_maintenance_log_spares_status",
            "tcb_manufacturing_customizations.doc_events.stock_entry.flagJc",
        ],
    },
    "Purchase Receipt": {
        # "on_submit":"tcb_manufacturing_customizations.doc_events.purchase_receipt.on_submit"
        # "after_insert":[
            # "tcb_manufacturing_customizations.doc_events.purchase_receipt.linkpo"
        # ],
        "validate": [
            # "tcb_manufacturing_customizations.doc_events.purchase_receipt.linkpo",
            "tcb_manufacturing_customizations.doc_events.purchase_receipt.validate",
            "tcb_manufacturing_customizations.doc_events.purchase_receipt.check_before_submit",
            # "tcb_manufacturing_customizations.doc_events.purchase_receipt.qc_check",
        ],
        "on_submit": [
            "tcb_manufacturing_customizations.doc_events.purchase_receipt.set_container_data",
            "tcb_manufacturing_customizations.doc_events.purchase_receipt.update_batches",
            "tcb_manufacturing_customizations.doc_events.purchase_receipt.create_import_bales",
        ],
        "on_cancel": ["tcb_manufacturing_customizations.doc_events.purchase_receipt.cancel_import_bales",
                      "tcb_manufacturing_customizations.doc_events.purchase_receipt.removeporef"
                      ],
        # REMOVE TAXES
        # "before_insert": "tcb_manufacturing_customizations.doc_events.sales_order.rem_taxes",
    },
    "Purchase Order": {
        # REMOVE TAXES
        # "before_insert": "tcb_manufacturing_customizations.doc_events.sales_order.rem_taxes",
    },
    "Purchase Invoice": {
        # REMOVE TAXES
        # "before_insert": "tcb_manufacturing_customizations.doc_events.sales_order.rem_taxes",
    },
    "BOM": {"validate": "tcb_manufacturing_customizations.doc_events.bom.validate"},
    "Delivery Estimate": {
        # "validate":"tcb_manufacturing_customizations.doc_events.delivery_estimate.check_employees"
    },
    "Work Order": {
        # "after_insert":"tcb_manufacturing_customizations.doc_events.work_order.check_warehouse",
        "before_insert": "tcb_manufacturing_customizations.doc_events.work_order.before_insert",
        "after_insert": [
            "tcb_manufacturing_customizations.doc_events.work_order.check_warehouse"
        ],
        "validate": "tcb_manufacturing_customizations.doc_events.work_order.validate",
    },
    "Quality Inspection": {
        "validate": "tcb_manufacturing_customizations.doc_events.quality_inspection.validate"
    },
    "Batch": {
        # "on_update":"tcb_manufacturing_customizations.doc_events.bom.on_update"
    },
    "Item": {
        "before_insert": "tcb_manufacturing_customizations.utils.item_property_utils.auto_add_properties_to_new_item",
    },
    "Stock Reconciliation": {
        "on_submit": "tcb_manufacturing_customizations.doc_events.stock_reconciliation.sync_sub_batch"
    },
    "Delivery Note": {
        "validate": "tcb_manufacturing_customizations.doc_events.delivery_note.fetch_bales",
        "on_submit": "tcb_manufacturing_customizations.doc_events.delivery_note.update_bales_status_on_dispatch",
        "on_trash": "tcb_manufacturing_customizations.doc_events.delivery_note.delete_linked_bales_doc",
        # "before_insert": "tcb_manufacturing_customizations.doc_events.sales_order.rem_taxes",
    },
    "Sales Order": {
        # REMOVE TAXES
        # "before_insert": "tcb_manufacturing_customizations.doc_events.sales_order.rem_taxes"
    },
    "Sales Invoice": {
        # REMOVE TAXES
        # "before_insert": "tcb_manufacturing_customizations.doc_events.sales_order.rem_taxes",
        "validate": "tcb_manufacturing_customizations.doc_events.sales_invoice.copy_bales_from_delivery_note",
    },
    # "Production Plan":{
    #     "validate":"tcb_manufacturing_customizations.doc_events.production_plan.nos_qty"
    # }
    # 	"*": {
    # 		"on_update": "method",
    # 		"on_cancel": "method",
    # 		"on_trash": "method"
    # 	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    # "cron":{
    #     "* * * * *":[
    #         "tcb_manufacturing_customizations.doc_events.delivery_estimate.get_supplier_wise_lead_time_of_items_cron"
    #         ]
    # },
    # "all": [
    #     "tcb_manufacturing_customizations.doc_events.delivery_estimate.get_supplier_wise_lead_time_of_items_cron"
    # ],
    "daily": [
        "tcb_manufacturing_customizations.doc_events.delivery_estimate.get_supplier_wise_lead_time_of_items_cron"
    ],
    # "hourly": [
    # 	"tcb_manufacturing_customizations.tasks.hourly"
    # ],
    # "weekly": [
    # 	"tcb_manufacturing_customizations.tasks.weekly"
    # ],
    # "monthly": [
    # 	"tcb_manufacturing_customizations.tasks.monthly"
    # ],
}

# Testing
# -------

# before_tests = "tcb_manufacturing_customizations.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "tcb_manufacturing_customizations.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "tcb_manufacturing_customizations.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["tcb_manufacturing_customizations.utils.before_request"]
# after_request = ["tcb_manufacturing_customizations.utils.after_request"]

# Job Events
# ----------
# before_job = ["tcb_manufacturing_customizations.utils.before_job"]
# after_job = ["tcb_manufacturing_customizations.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"tcb_manufacturing_customizations.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
