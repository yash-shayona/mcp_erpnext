app_name = "mcp_erpnext"
app_title = "MCP ERPNext"
app_publisher = "Your Organization"
app_description = "MCP tools for safe ERPNext workflows"
app_email = "dev@example.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "mcp_erpnext",
# 		"logo": "/assets/mcp_erpnext/logo.png",
# 		"title": "MCP ERPNext",
# 		"route": "/mcp_erpnext",
# 		"has_permission": "mcp_erpnext.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/mcp_erpnext/css/mcp_erpnext.css"
# app_include_js = "/assets/mcp_erpnext/js/mcp_erpnext.js"

# include js, css files in header of web template
# web_include_css = "/assets/mcp_erpnext/css/mcp_erpnext.css"
# web_include_js = "/assets/mcp_erpnext/js/mcp_erpnext.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "mcp_erpnext/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "mcp_erpnext/public/icons.svg"

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

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "mcp_erpnext.utils.jinja_methods",
# 	"filters": "mcp_erpnext.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "mcp_erpnext.install.before_install"
# after_install = "mcp_erpnext.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "mcp_erpnext.uninstall.before_uninstall"
# after_uninstall = "mcp_erpnext.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "mcp_erpnext.utils.before_app_install"
# after_app_install = "mcp_erpnext.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "mcp_erpnext.utils.before_app_uninstall"
# after_app_uninstall = "mcp_erpnext.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "mcp_erpnext.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "mcp_erpnext.notifications.get_notification_config"

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

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"mcp_erpnext.tasks.all"
# 	],
# 	"daily": [
# 		"mcp_erpnext.tasks.daily"
# 	],
# 	"hourly": [
# 		"mcp_erpnext.tasks.hourly"
# 	],
# 	"weekly": [
# 		"mcp_erpnext.tasks.weekly"
# 	],
# 	"monthly": [
# 		"mcp_erpnext.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "mcp_erpnext.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "mcp_erpnext.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "mcp_erpnext.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "mcp_erpnext.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["mcp_erpnext.utils.before_request"]
# after_request = ["mcp_erpnext.utils.after_request"]

# Job Events
# ----------
# before_job = ["mcp_erpnext.utils.before_job"]
# after_job = ["mcp_erpnext.utils.after_job"]

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
# 	"mcp_erpnext.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
