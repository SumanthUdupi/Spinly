"""
ETA engine — machine allocation + estimated completion datetime.

Algorithm:
1. Filter machines: status in (Idle, Running), skip Maintenance/Out of Order
2. Sort by current_load_kg ASC (Silver/Gold get least-loaded = earliest ETA)
3. For each eligible machine: check capacity, compute T_queue + T_service
4. If ETA > shift_end: roll to next-day shift_start + overflow
5. Fallback: pick machine with earliest countdown_timer_end
"""
import frappe
from frappe.utils import now_datetime, add_to_date, get_datetime
from datetime import datetime, timedelta


def assign_machine_and_eta(order) -> None:
    """
    Mutates order.assigned_machine and order.expected_ready_date in-place.
    Called from logic/order.py → before_save.
    """
    if not order.service or not order.total_weight_kg:
        return

    service = frappe.get_cached_doc("Laundry Service", order.service)
    processing_minutes = service.processing_minutes or 0

    settings = frappe.get_cached_doc("Spinly Settings")
    shift_start_str = settings.shift_start or "08:00:00"
    shift_duration_hrs = settings.shift_duration_hrs or 10

    customer_tier = _get_customer_tier(order.customer)

    machines = _get_eligible_machines(order.total_weight_kg)
    if not machines:
        order.expected_ready_date = _fallback_eta(processing_minutes, shift_start_str, shift_duration_hrs)
        return

    now = now_datetime()
    shift_end = _shift_end(now, shift_start_str, shift_duration_hrs)

    best_machine = None
    best_eta = None

    for m in machines:
        t_queue = _get_queue_minutes(m["name"])
        eta = add_to_date(now, minutes=t_queue + processing_minutes)

        if get_datetime(eta) > get_datetime(shift_end):
            overflow = (get_datetime(eta) - get_datetime(shift_end)).total_seconds() / 60
            next_start = _next_shift_start(shift_start_str)
            eta = add_to_date(next_start, minutes=overflow)

        if best_eta is None or get_datetime(eta) < get_datetime(best_eta):
            best_eta = eta
            best_machine = m["name"]

    order.assigned_machine = best_machine
    order.expected_ready_date = best_eta


# ── private helpers ──────────────────────────────────────────────────────────

def _get_eligible_machines(order_weight_kg: float) -> list:
    """Return machines sorted by current_load_kg ASC that can accept the order weight."""
    all_machines = frappe.get_all(
        "Laundry Machine",
        filters={"status": ["in", ["Idle", "Running"]]},
        fields=["name", "capacity_kg", "current_load_kg", "countdown_timer_end"],
        order_by="current_load_kg asc",
    )
    return [
        m for m in all_machines
        if (m["current_load_kg"] or 0) + order_weight_kg <= (m["capacity_kg"] or 0)
    ]


def _get_queue_minutes(machine_name: str) -> float:
    """
    Sum remaining processing time for all active Job Cards on this machine.
    Active = submitted (docstatus=1) with workflow_state not in (Ready, Delivered).
    """
    active_jobs = frappe.db.sql(
        """
        SELECT jc.name, jc.start_time, ls.processing_minutes
        FROM `tabLaundry Job Card` jc
        JOIN `tabLaundry Order` lo ON lo.name = jc.laundry_order
        JOIN `tabLaundry Service` ls ON ls.name = lo.service
        WHERE jc.assigned_machine = %s
          AND jc.docstatus = 1
          AND jc.workflow_state NOT IN ('Ready', 'Delivered', '')
        """,
        machine_name,
        as_dict=True,
    )
    now = now_datetime()
    total_remaining = 0.0
    for job in active_jobs:
        elapsed = 0.0
        if job.start_time:
            elapsed_td = now - get_datetime(job.start_time)
            elapsed = elapsed_td.total_seconds() / 60
        remaining = max(0, (job.processing_minutes or 0) - elapsed)
        total_remaining += remaining
    return total_remaining


def _shift_end(reference: datetime, shift_start_str: str, shift_duration_hrs: float) -> datetime:
    """Return today's shift end datetime."""
    today = reference.date()
    h, m, *_ = str(shift_start_str).split(":")
    start = datetime(today.year, today.month, today.day, int(h), int(m))
    return start + timedelta(hours=shift_duration_hrs)


def _next_shift_start(shift_start_str: str) -> datetime:
    """Return tomorrow's shift start datetime."""
    from frappe.utils import add_days
    now = now_datetime()
    tomorrow = (now + timedelta(days=1)).date()
    h, m, *_ = str(shift_start_str).split(":")
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, int(h), int(m))


def _fallback_eta(processing_minutes: float, shift_start_str: str, shift_duration_hrs: float) -> str:
    """No eligible machine — find the machine with the earliest countdown_timer_end."""
    machines = frappe.get_all(
        "Laundry Machine",
        filters={"status": ["in", ["Idle", "Running"]]},
        fields=["countdown_timer_end"],
        order_by="countdown_timer_end asc",
    )
    now = now_datetime()
    base = now
    if machines and machines[0].get("countdown_timer_end"):
        base = get_datetime(machines[0]["countdown_timer_end"])
    eta = add_to_date(base, minutes=processing_minutes)
    return str(eta)


def _get_customer_tier(customer: str) -> str:
    if not customer:
        return "Bronze"
    tier = frappe.db.get_value("Loyalty Account", {"customer": customer}, "tier")
    return tier or "Bronze"
