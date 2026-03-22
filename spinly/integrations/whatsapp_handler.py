"""
WhatsApp integration — outbound message dispatch.
All sends are fire-and-forget; failures are logged to WhatsApp Message Log.
"""
import frappe
import requests
from frappe.utils import today, add_days


def send_order_confirmation(doc, method=None):
    """Hook: fires on Laundry Order on_submit. Sends order confirmation WA."""
    try:
        customer = frappe.get_doc("Laundry Customer", doc.customer)
        _enqueue_message(
            customer=customer,
            message_type="Order Confirmation",
            context={
                "lot_number": doc.lot_number or "",
                "eta": str(doc.expected_ready_date or "TBD"),
                "total_amount": doc.grand_total or 0,
                "upi_link": _upi_link(doc.grand_total),
            },
            reference_doctype="Laundry Order",
            reference_name=doc.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Order Confirmation WhatsApp Failed")


def on_payment_confirmed(doc, method=None):
    """Hook: fires on Laundry Order on_update. Sends Payment Thanks only on Unpaid→Paid."""
    if doc.payment_status != "Paid":
        return
    doc_before = doc.get_doc_before_save()
    if doc_before and doc_before.payment_status == "Paid":
        return  # already was Paid — suppress duplicate
    try:
        customer = frappe.get_doc("Laundry Customer", doc.customer)
        _enqueue_message(
            customer=customer,
            message_type="Payment Thanks",
            context={
                "customer_name": customer.full_name,
                "total_amount": doc.grand_total or 0,
            },
            reference_doctype="Laundry Order",
            reference_name=doc.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Payment Thanks WhatsApp Failed")


def send_pickup_reminder_for_order(order):
    """Send pickup reminder when a Job Card reaches Ready state."""
    customer = frappe.get_doc("Laundry Customer", order.customer)
    _enqueue_message(
        customer=customer,
        message_type="Pickup Reminder",
        context={"order": order.name},
        reference_doctype="Laundry Order",
        reference_name=order.name,
    )


def send_delivery_notification(order):
    """Send 'Order Confirmation / Payment Thanks' on delivery."""
    customer = frappe.get_doc("Laundry Customer", order.customer)
    _enqueue_message(
        customer=customer,
        message_type="Payment Thanks",
        context={"order": order.name, "grand_total": order.grand_total},
        reference_doctype="Laundry Order",
        reference_name=order.name,
    )


def send_pickup_reminders():
    """Daily: remind customers whose orders have been Ready for > 1 day."""
    orders = frappe.db.sql(
        """SELECT name, customer FROM `tabLaundry Order`
           WHERE status='Ready' AND DATE(expected_ready_date) <= %s AND docstatus=1""",
        today(),
        as_dict=True,
    )
    for o in orders:
        customer = frappe.get_doc("Laundry Customer", o.customer)
        _enqueue_message(
            customer=customer,
            message_type="Pickup Reminder",
            context={"order": o.name},
            reference_doctype="Laundry Order",
            reference_name=o.name,
        )


def send_win_back_messages():
    """Daily: message customers inactive for win_back_after_days."""
    settings = frappe.get_cached_doc("Spinly Settings")
    days = settings.win_back_after_days or 30
    cutoff = add_days(today(), -days)

    inactive = frappe.db.sql(
        """SELECT DISTINCT customer FROM `tabLaundry Order`
           GROUP BY customer
           HAVING MAX(DATE(order_date)) < %s""",
        cutoff,
        as_dict=True,
    )
    for row in inactive:
        customer = frappe.get_doc("Laundry Customer", row.customer)
        _enqueue_message(
            customer=customer,
            message_type="Win-Back",
            context={},
            reference_doctype="Laundry Customer",
            reference_name=row.customer,
        )


# ── private helpers ──────────────────────────────────────────────────────────

def _enqueue_message(customer, message_type: str, context: dict,
                     reference_doctype=None, reference_name=None):
    """Create a WhatsApp Message Log entry and attempt to send."""
    template = frappe.db.get_value(
        "WhatsApp Message Template",
        {"message_type": message_type, "language": customer.language_preference or None},
    )
    if not template:
        template = frappe.db.get_value(
            "WhatsApp Message Template", {"message_type": message_type}
        )

    body = _render_template(template, context) if template else f"[{message_type}]"

    log = frappe.new_doc("WhatsApp Message Log")
    log.customer = customer.name
    log.phone_number = customer.phone
    log.template = template
    log.message_type = message_type
    log.message_body = body
    log.reference_doctype = reference_doctype
    log.reference_name = reference_name
    log.insert(ignore_permissions=True)

    _dispatch(log, body, customer.phone)


def _dispatch(log, body: str, phone: str):
    """Send via WhatsApp API and update log status."""
    settings = frappe.get_cached_doc("Spinly Settings")
    api_url = settings.whatsapp_api_url
    api_key = settings.get_password("whatsapp_api_key") if settings.whatsapp_api_key else None

    if not api_url or not api_key:
        # Stub mode — log as Queued (Phase 2: swap provider details in Settings)
        frappe.db.set_value("WhatsApp Message Log", log.name, "status", "Queued")
        return

    try:
        resp = requests.post(
            api_url,
            json={"phone": phone, "message": body},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        frappe.db.set_value("WhatsApp Message Log", log.name, "status", "Sent")
    except Exception as e:
        frappe.db.set_value("WhatsApp Message Log", log.name, "status", "Failed")
        frappe.db.set_value("WhatsApp Message Log", log.name, "error_message", str(e))


def _upi_link(amount) -> str:
    """Build a UPI deep-link string for the invoice amount."""
    upi_id = frappe.db.get_single_value("Spinly Settings", "upi_id") or ""
    if not upi_id:
        return ""
    return f"upi://pay?pa={upi_id}&am={amount or 0}&cu=INR"


def _render_template(template_name: str, context: dict) -> str:
    if not template_name:
        return ""
    tpl = frappe.get_cached_doc("WhatsApp Message Template", template_name)
    body = tpl.template_body or ""
    for k, v in context.items():
        body = body.replace(f"{{{{{k}}}}}", str(v))
    return body
