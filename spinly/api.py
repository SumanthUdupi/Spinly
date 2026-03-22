"""
Spinly whitelisted API endpoints.
All methods callable via frappe.call('spinly.api.<method>').
"""
import frappe
from frappe import _


# ── Customer ─────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False)
def get_customer_by_phone(phone: str) -> dict:
    """Look up a customer by phone number for POS Screen 1."""
    customer = frappe.db.get_value(
        "Laundry Customer",
        {"phone": phone},
        ["name", "full_name", "phone"],
        as_dict=True,
    )
    if not customer:
        return {}
    loyalty = frappe.db.get_value(
        "Loyalty Account",
        {"customer": customer["name"]},
        ["current_balance", "tier"],
        as_dict=True,
    ) or {"current_balance": 0, "tier": "Bronze"}
    customer.update(loyalty)
    return customer


@frappe.whitelist(allow_guest=False)
def create_customer(full_name: str, phone: str) -> dict:
    """Create a new Laundry Customer + Loyalty Account from POS."""
    import re
    if not phone or not re.fullmatch(r"\d{7,15}", phone.strip()):
        frappe.throw(_("Phone number must be 7–15 digits."))
    phone = phone.strip()
    if not full_name or not full_name.strip():
        frappe.throw(_("Full name is required."))
    if frappe.db.exists("Laundry Customer", {"phone": phone}):
        frappe.throw(_("A customer with phone {0} already exists.").format(phone))

    cust = frappe.new_doc("Laundry Customer")
    cust.full_name = full_name
    cust.phone = phone
    cust.insert(ignore_permissions=True)

    # Auto-create loyalty account
    from spinly.logic.loyalty import _ensure_loyalty_account
    _ensure_loyalty_account(cust.name)

    return {"name": cust.name, "full_name": cust.full_name, "phone": cust.phone,
            "current_balance": 0, "tier": "Bronze"}


# ── Masters ──────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False)
def get_pos_masters() -> dict:
    """Return all active masters needed to render POS Screens 1–3 in one call."""
    garments = frappe.get_all(
        "Garment Type",
        filters={"is_active": 1},
        fields=["name", "garment_name", "icon_emoji", "default_weight_kg", "sort_order"],
        order_by="sort_order asc",
    )
    services = frappe.get_all(
        "Laundry Service",
        fields=["name", "service_name", "service_type", "base_price_per_kg", "processing_minutes"],
        order_by="service_name asc",
    )
    alert_tags = frappe.get_all(
        "Alert Tag",
        filters={"is_active": 1},
        fields=["name", "tag_name", "color_code", "icon_emoji", "sort_order"],
        order_by="sort_order asc",
    )
    payment_methods = frappe.get_all(
        "Payment Method",
        filters={"is_active": 1},
        fields=["name", "method_name", "show_upi_qr", "sort_order"],
        order_by="sort_order asc",
    )
    settings = frappe.db.get_singles_dict("Spinly Settings")
    return {
        "garments": garments,
        "services": services,
        "alert_tags": alert_tags,
        "payment_methods": payment_methods,
        "currency_symbol": settings.get("currency_symbol", "₹"),
        "upi_id": settings.get("upi_id", ""),
    }


# ── Order ────────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False)
def preview_order(customer: str, service: str, items: str | list, alert_tag_names: str | list | None = None) -> dict:
    """
    Compute pricing + ETA for the order builder preview (Screen 2 → 3 transition).
    Does NOT save anything to DB.
    """
    import json
    if isinstance(items, str):
        items = json.loads(items)
    if isinstance(alert_tag_names, str):
        alert_tag_names = json.loads(alert_tag_names) if alert_tag_names else []

    service_doc = frappe.get_cached_doc("Laundry Service", service)
    price_per_kg = service_doc.base_price_per_kg or 0.0

    total_weight = 0.0
    total_items = 0
    line_items = []
    for row in items:
        qty = int(row.get("quantity", 0))
        wt = float(row.get("weight_kg", 0))
        line_total = round(wt * qty * price_per_kg, 2)
        total_weight += wt * qty
        total_items += qty
        line_items.append({**row, "unit_price": price_per_kg, "line_total": line_total})

    subtotal = round(sum(r["line_total"] for r in line_items), 2)
    settings = frappe.get_cached_doc("Spinly Settings")

    # Promo discount preview
    promo_disc = 0.0
    promo_name = None
    promo_label = None
    try:
        from spinly.logic.loyalty import _apply_best_discount as _promo

        class _FakeDoc:
            pass
        fdoc = _FakeDoc()
        fdoc.customer = customer
        fdoc.service = service
        fdoc.total_weight_kg = total_weight
        fdoc.subtotal = subtotal
        fdoc.applied_promo = None
        fdoc.promo_discount_amount = 0
        _promo(fdoc)
        promo_disc = fdoc.promo_discount_amount or 0
        promo_name = fdoc.applied_promo
        if promo_name:
            promo_label = frappe.db.get_value("Promo Campaign", promo_name, "campaign_name")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "preview_order: promo calculation failed")

    net_amount = round(max(0, subtotal - promo_disc), 2)
    tax_rate = (settings.tax_rate_pct or 0) / 100
    tax_amount = round(net_amount * tax_rate, 2)
    grand_total = round(net_amount + tax_amount, 2)

    # Loyalty balance and redeemable monetary value
    loyalty_balance = frappe.db.get_value(
        "Loyalty Account", {"customer": customer}, "current_balance"
    ) or 0
    redemption_rate = int(settings.redemption_pts_per_rupee or 10)
    redeemable_amount = round(loyalty_balance / redemption_rate, 2)

    # ETA preview via a dummy order object
    class _FakeOrder:
        pass
    fake = _FakeOrder()
    fake.customer = customer
    fake.service = service
    fake.total_weight_kg = total_weight
    fake.assigned_machine = None
    fake.expected_ready_date = None
    fake.discount_amount = promo_disc

    from spinly.logic.eta_calc import assign_machine_and_eta
    assign_machine_and_eta(fake)

    return {
        "items": line_items,
        "total_weight_kg": round(total_weight, 3),
        "total_items": total_items,
        "subtotal": subtotal,
        "promo_discount": promo_disc,
        "promo_name": promo_name,
        "promo_label": promo_label,
        "tax_amount": tax_amount,
        "grand_total": grand_total,
        "assigned_machine": fake.assigned_machine,
        "expected_ready_date": str(fake.expected_ready_date) if fake.expected_ready_date else None,
        "loyalty_balance": loyalty_balance,
        "redeemable_amount": redeemable_amount,
        "redemption_rate": redemption_rate,
    }


@frappe.whitelist(allow_guest=False)
def submit_order(customer: str, service: str, items: str | list,
                  alert_tag_names: str | list | None = None,
                  payment_method: str | None = None,
                  apply_loyalty_points: int = 0,
                  special_instructions: str = "") -> dict:
    """Create and submit a Laundry Order. Returns order + job_card names."""
    import json
    if isinstance(items, str):
        items = json.loads(items)
    if isinstance(alert_tag_names, str):
        alert_tag_names = json.loads(alert_tag_names) if alert_tag_names else []

    order = frappe.new_doc("Laundry Order")
    order.customer = customer
    order.service = service
    order.order_date = frappe.utils.today()
    order.payment_method = payment_method
    order.special_instructions = special_instructions

    for row in items:
        order.append("items", {
            "garment_type": row["garment_type"],
            "quantity": int(row["quantity"]),
            "weight_kg": float(row["weight_kg"]),
        })

    for tag_name in (alert_tag_names or []):
        order.append("alert_tags", {"alert_tag": tag_name})

    # Set loyalty points to redeem — _apply_pricing (via before_save) converts to monetary discount
    if apply_loyalty_points and apply_loyalty_points > 0:
        # Validate against actual balance
        balance = frappe.db.get_value(
            "Loyalty Account", {"customer": customer}, "current_balance"
        ) or 0
        order.loyalty_points_redeemed = min(int(apply_loyalty_points), int(balance))

    order.insert(ignore_permissions=True)
    order.submit()

    # Record the redemption debit transaction
    if order.loyalty_points_redeemed and order.loyalty_points_redeemed > 0:
        from spinly.logic.loyalty import _add_transaction, _update_balance
        _add_transaction(
            customer=customer,
            transaction_type="Debit",
            points=order.loyalty_points_redeemed,
            reference_doctype="Laundry Order",
            reference_name=order.name,
            notes="Redeemed at POS",
        )
        _update_balance(customer)

    # Get the auto-created job card
    jc_name = frappe.db.get_value("Laundry Job Card", {"laundry_order": order.name}, "name")

    return {"order": order.name, "job_card": jc_name, "lot_number": order.lot_number,
            "grand_total": order.grand_total, "expected_ready_date": str(order.expected_ready_date or "")}


# ── Job Card ─────────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=False)
def get_job_card(job_card: str) -> dict:
    """Return full job card data for the advancement screen."""
    jc = frappe.get_doc("Laundry Job Card", job_card)
    order = frappe.get_doc("Laundry Order", jc.laundry_order)
    tag_names = [row.alert_tag for row in order.alert_tags if row.alert_tag]
    tag_map = {}
    if tag_names:
        for row in frappe.get_all(
            "Alert Tag",
            filters={"name": ("in", tag_names)},
            fields=["name", "tag_name", "color_code", "icon_emoji"],
        ):
            tag_map[row.name] = row
    alert_tags = [
        {
            "tag_name": tag_map.get(row.alert_tag, {}).get("tag_name", ""),
            "color_code": tag_map.get(row.alert_tag, {}).get("color_code", ""),
            "icon_emoji": tag_map.get(row.alert_tag, {}).get("icon_emoji", ""),
        }
        for row in order.alert_tags
        if row.alert_tag
    ]
    machine_name = frappe.db.get_value("Laundry Machine", jc.assigned_machine, "machine_name") if jc.assigned_machine else ""
    return {
        "name": jc.name,
        "lot_number": jc.lot_number,
        "customer_tier_badge": jc.customer_tier_badge,
        "workflow_state": jc.workflow_state or "Sorting",
        "assigned_machine": jc.assigned_machine,
        "machine_name": machine_name,
        "special_instructions": jc.special_instructions,
        "alert_tags": alert_tags,
        "payment_status": order.payment_status,
        "grand_total": order.grand_total,
        "laundry_order": order.name,
    }


@frappe.whitelist(allow_guest=False)
def advance_job_card(job_card: str, action: str) -> dict:
    """Apply a workflow action to a Job Card."""
    from frappe.model.workflow import apply_workflow
    doc = frappe.get_doc("Laundry Job Card", job_card)
    apply_workflow(doc, action)
    return {"workflow_state": doc.workflow_state}


@frappe.whitelist(allow_guest=False)
def mark_order_paid(order_name: str, payment_method: str) -> dict:
    """Toggle order payment status to Paid."""
    order = frappe.get_doc("Laundry Order", order_name)
    order.payment_status = "Paid"
    order.payment_method = payment_method
    order.save(ignore_permissions=True)

    # Trigger WhatsApp payment thanks
    try:
        from spinly.integrations.whatsapp_handler import send_delivery_notification
        send_delivery_notification(order)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Payment Thanks WhatsApp Failed")

    return {"status": "Paid"}


@frappe.whitelist(allow_guest=False)
def get_active_job_cards() -> list:
    """Return all non-delivered job cards for the live tracking view."""
    return frappe.db.sql(
        """
        SELECT jc.name, jc.lot_number, jc.workflow_state, jc.customer_tier_badge,
               jc.assigned_machine, lm.machine_name,
               lo.customer, lc.full_name as customer_name,
               lo.grand_total, lo.payment_status
        FROM `tabLaundry Job Card` jc
        JOIN `tabLaundry Order` lo ON lo.name = jc.laundry_order
        JOIN `tabLaundry Customer` lc ON lc.name = lo.customer
        LEFT JOIN `tabLaundry Machine` lm ON lm.name = jc.assigned_machine
        WHERE jc.docstatus = 1
          AND (jc.workflow_state IS NULL OR jc.workflow_state NOT IN ('Delivered', ''))
        ORDER BY jc.creation DESC
        LIMIT 50
        """,
        as_dict=True,
    )
