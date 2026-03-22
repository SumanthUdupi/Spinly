"""
Laundry Order business logic.
Hooked via doc_events in hooks.py.
"""
import frappe
from frappe.model.naming import make_autoname


def before_save(doc, method=None):
    """Recalculate totals, apply promo, apply pricing, assign ETA."""
    if not doc.lot_number:
        doc.lot_number = make_autoname("LOT-.YYYY.-.#####")
    _recalculate_totals(doc)
    # Apply best promo BEFORE pricing so discount is baked into grand_total
    from spinly.logic.loyalty import apply_best_discount
    apply_best_discount(doc)
    _apply_pricing(doc)
    # ETA + machine allocation (only for new/unsaved orders)
    if doc.docstatus == 0:
        from spinly.logic.eta_calc import assign_machine_and_eta
        assign_machine_and_eta(doc)


def on_submit(doc, method=None):
    """Auto-create Job Card and deduct consumables."""
    _create_job_card(doc)
    from spinly.logic.inventory import deduct_for_order
    deduct_for_order(doc)


def on_cancel(doc, method=None):
    """Release machine load and restore consumable inventory on cancel."""
    if doc.assigned_machine:
        _release_machine_load(doc)
    from spinly.logic.inventory import restore_for_order
    restore_for_order(doc)


# ── private helpers ──────────────────────────────────────────────────────────

def _recalculate_totals(doc):
    total_weight = 0.0
    total_items = 0
    for row in doc.items:
        qty = row.quantity or 0
        wt = row.weight_kg or 0
        total_weight += wt * qty
        total_items += qty
    doc.total_weight_kg = round(total_weight, 3)
    doc.total_items = total_items


def _apply_pricing(doc):
    """
    Compute line totals, subtotal, discounts, tax, net_amount, grand_total.

    Discount priority (all can stack):
      1. Tier discount  — Silver 5%, Gold 10% (from Spinly Settings)
      2. Promo discount — set by apply_best_discount() before this call
      3. Loyalty redemption — points_redeemed / redemption_pts_per_rupee
    """
    if not doc.service:
        return

    service = frappe.get_cached_doc("Laundry Service", doc.service)
    price_per_kg = service.base_price_per_kg or 0.0

    for row in doc.items:
        row.unit_price = price_per_kg
        row.line_total = round((row.weight_kg or 0) * (row.quantity or 0) * price_per_kg, 2)

    subtotal = round(sum(r.line_total for r in doc.items), 2)
    doc.subtotal = subtotal

    settings = frappe.get_cached_doc("Spinly Settings")

    # Tier discount
    tier = _get_customer_tier(doc.customer)
    tier_disc_pct = 0.0
    if tier == "Gold":
        tier_disc_pct = float(settings.tier_gold_discount_pct or 0)
    elif tier == "Silver":
        tier_disc_pct = float(settings.tier_silver_discount_pct or 0)
    tier_disc = round(subtotal * tier_disc_pct / 100, 2)

    # Loyalty redemption monetary value
    redemption_rate = int(settings.redemption_pts_per_rupee or 10)
    loyalty_disc = round((doc.loyalty_points_redeemed or 0) / redemption_rate, 2)

    # Promo discount (set before this call by apply_best_discount)
    promo_disc = doc.promo_discount_amount or 0

    # Total discount = tier + promo + loyalty redemption
    doc.discount_amount = round(tier_disc + promo_disc + loyalty_disc, 2)

    # Store tier and promo amounts separately for invoice display
    doc.tier_discount_amount = tier_disc
    doc.promo_discount_amount = promo_disc  # keep (already set)

    # net_amount after all discounts (floor 0)
    doc.net_amount = round(max(0, subtotal - doc.discount_amount), 2)

    tax_rate = (settings.tax_rate_pct or 0) / 100
    doc.tax_amount = round(doc.net_amount * tax_rate, 2)
    doc.grand_total = round(doc.net_amount + doc.tax_amount, 2)


def _create_job_card(doc):
    tier = _get_customer_tier(doc.customer)

    jc = frappe.new_doc("Laundry Job Card")
    jc.laundry_order = doc.name
    jc.assigned_machine = doc.assigned_machine
    jc.customer_tier_badge = tier
    jc.insert(ignore_permissions=True)


def _release_machine_load(doc):
    machine = frappe.get_doc("Laundry Machine", doc.assigned_machine)
    machine.current_load_kg = max(0, (machine.current_load_kg or 0) - (doc.total_weight_kg or 0))
    if machine.current_load_kg <= 0:
        machine.status = "Idle"
    machine.save(ignore_permissions=True)


def _get_customer_tier(customer: str) -> str:
    if not customer:
        return "Bronze"
    tier = frappe.db.get_value("Loyalty Account", {"customer": customer}, "tier")
    return tier or "Bronze"
