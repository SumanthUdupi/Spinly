"""
Machine management — timer housekeeping.
"""
import frappe
from frappe.utils import now_datetime


def clear_completed_timers():
    """Hourly job: set machines to Idle when countdown timer has passed."""
    machines = frappe.get_all(
        "Laundry Machine",
        filters={"status": "Running"},
        fields=["name", "countdown_timer_end"],
    )
    now = now_datetime()
    updated = False
    for m in machines:
        if m.countdown_timer_end and m.countdown_timer_end <= now:
            frappe.db.set_value("Laundry Machine", m.name, {
                "status": "Idle",
                "current_load_kg": 0,
            })
            updated = True
    if updated:
        frappe.db.commit()
