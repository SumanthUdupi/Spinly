app_name = "spinly"
app_title = "Spinly"
app_publisher = "Spinly"
app_description = "Spinly Laundry Management System"
app_email = "dev@spinly.com"
app_license = "mit"

# Fixtures — exported via bench export-fixtures / loaded via bench migrate
fixtures = [
    "Consumable Category",
    "Garment Type",
    "Alert Tag",
    "Payment Method",
    "Laundry Service",
    {"dt": "Language", "filters": [["name", "in", ["en", "hi", "mr"]]]},
    "WhatsApp Message Template",
    "Laundry Machine",
    "Laundry Consumable",
    "Spinly Settings",
    {"dt": "Workflow State", "filters": [["workflow_state_name", "in", [
        "Sorting", "Washing", "Drying", "Ironing", "Ready", "Delivered"
    ]]]},
    {"dt": "Workflow Action Master", "filters": [["workflow_action_name", "in", [
        "Start Washing", "Start Drying", "Start Ironing", "Mark Ready", "Mark Delivered"
    ]]]},
    {"dt": "Workflow", "filters": [["document_type", "=", "Laundry Job Card"]]},
    {"dt": "Print Format", "filters": [["name", "in", ["Job Tag Thermal", "Spinly Customer Invoice"]]]},
    "Promo Campaign",
    "Laundry Customer",
    "Loyalty Account",
    "Loyalty Transaction",  # must come after Loyalty Account (FK dependency)
]

# Authentication — redirect staff to POS on login
on_login = "spinly.auth.redirect_staff_to_pos"

# Document Events
doc_events = {
    "Laundry Customer": {
        "after_insert": "spinly.logic.loyalty.ensure_loyalty_account_on_insert",
    },
    "Laundry Order": {
        "before_save": "spinly.logic.order.before_save",
        "on_submit": [
            "spinly.logic.order.on_submit",
            "spinly.logic.loyalty.credit_order_points_on_submit",
            "spinly.integrations.whatsapp_handler.send_order_confirmation",
            "spinly.integrations.whatsapp_handler.send_vip_thank_you",
        ],
        "on_cancel": "spinly.logic.order.on_cancel",
        "on_update": "spinly.integrations.whatsapp_handler.on_payment_confirmed",
    },
    "Laundry Job Card": {
        "on_submit": "spinly.logic.job_card.on_submit",
        "on_workflow_action": "spinly.logic.job_card.on_workflow_action",
    },
    "Inventory Restock Log": {
        "after_insert": "spinly.logic.inventory.on_restock",
    },
}

# Scheduled Tasks
scheduler_events = {
    "daily": [
        "spinly.logic.loyalty.expire_points",
        "spinly.logic.inventory.check_low_stock",
        "spinly.integrations.whatsapp_handler.send_pickup_reminders",
        "spinly.integrations.whatsapp_handler.send_win_back_messages",
        "spinly.integrations.whatsapp_handler.send_birthday_messages",
    ],
    "hourly": [
        "spinly.logic.machine.clear_completed_timers",
    ],
    "weekly": [
        "spinly.logic.loyalty.evaluate_streaks",
    ],
    "monthly": [
        "spinly.logic.loyalty.recalculate_all_tiers",
    ],
}

# Export type annotations
export_python_type_annotations = True
require_type_annotated_api_methods = True
