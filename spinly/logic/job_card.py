"""
Laundry Job Card business logic.
Hooked via doc_events in hooks.py.

Lifecycle:
  - Job Card is auto-created (insert, docstatus=0) at Sorting state.
  - Staff advance via Frappe Workflow actions (on_workflow_action fires each step).
  - At "Delivered" the Frappe Workflow sets docstatus=1 (submitted); on_submit fires.
"""
import frappe
from frappe.utils import now_datetime


def on_submit(doc, method=None):
    """Fires when Job Card reaches Delivered state (docstatus 0→1)."""
    doc.db_set("end_time", now_datetime())
    _update_order_status(doc, "Delivered")
    frappe.db.set_value("Laundry Order", doc.laundry_order, "actual_delivery_date", now_datetime())
    if doc.assigned_machine:
        _update_machine_load(doc, add=False)
    _maybe_issue_scratch_card(doc)   # moved here from on_workflow_action


def on_workflow_action(doc, method=None):
    """Fires on every workflow transition except the final submit."""
    state = doc.workflow_state

    if state == "Sorting":
        # Just entered Sorting — set start time, reserve machine load
        doc.db_set("start_time", now_datetime())
        if doc.assigned_machine:
            _update_machine_load(doc, add=True)
        _update_order_status(doc, "Sorting")

    elif state == "Washing":
        _set_machine_status(doc, "Running")
        _update_order_status(doc, "Processing")

    elif state == "Ready":
        _update_order_status(doc, "Ready")
        _send_pickup_reminder(doc)


# ── private helpers ──────────────────────────────────────────────────────────

def _update_machine_load(doc, add: bool):
    if not doc.assigned_machine:
        return
    machine = frappe.get_doc("Laundry Machine", doc.assigned_machine)
    delta = doc.total_weight_kg or 0
    if add:
        machine.current_load_kg = (machine.current_load_kg or 0) + delta
        machine.status = "Running"
    else:
        machine.current_load_kg = max(0, (machine.current_load_kg or 0) - delta)
        if machine.current_load_kg <= 0:
            machine.status = "Idle"
    machine.save(ignore_permissions=True)


def _set_machine_status(doc, status: str):
    if doc.assigned_machine:
        frappe.db.set_value("Laundry Machine", doc.assigned_machine, "status", status)


def _update_order_status(doc, status: str):
    frappe.db.set_value("Laundry Order", doc.laundry_order, "status", status)


def _send_pickup_reminder(doc):
    try:
        from spinly.integrations.whatsapp_handler import send_pickup_reminder_for_order
        order = frappe.get_doc("Laundry Order", doc.laundry_order)
        send_pickup_reminder_for_order(order)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Pickup Reminder Failed")


def _maybe_issue_scratch_card(doc):
    try:
        from spinly.logic.loyalty import maybe_issue_scratch_card
        order = frappe.get_doc("Laundry Order", doc.laundry_order)
        maybe_issue_scratch_card(order)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Scratch Card Issue Failed")


