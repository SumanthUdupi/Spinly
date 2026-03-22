"""
Loyalty points engine — earn, redeem, expire, streak, tier, promos, referrals.
"""
import frappe
from frappe.utils import today, add_days, getdate, nowdate
import random


# ── Hook-compatible entry points ─────────────────────────────────────────────

def ensure_loyalty_account_on_insert(doc, method=None):
    """Hook: Laundry Customer after_insert — ensures a Loyalty Account exists."""
    _ensure_loyalty_account(doc.name)


def credit_order_points_on_submit(doc, method=None):
    """Hook: Laundry Order on_submit — full earn_points flow."""
    try:
        earn_points(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Credit Order Points Failed")


def apply_best_discount(doc, method=None):
    """
    Called from order.py before_save (before _apply_pricing).
    Finds the highest-priority eligible Promo Campaign and sets:
      doc.applied_promo        → campaign name
      doc.promo_discount_amount → monetary discount
    Silently skips if no campaign matches or on any error.
    """
    if not doc.customer or not doc.service:
        return
    try:
        _apply_best_discount(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Apply Best Discount Failed")


# ── Core loyalty engine ───────────────────────────────────────────────────────

def earn_points(order):
    """
    Full points-earn flow triggered on Laundry Order submit.
    Credits points, updates tier, checks streak, handles referral on first order.
    """
    settings = frappe.get_cached_doc("Spinly Settings")
    _ensure_loyalty_account(order.customer)

    # Points = max(weight-based, amount-based)
    net = float(order.net_amount or order.grand_total or 0)
    pts_by_weight = float(order.total_weight_kg or 0) * float(settings.points_per_kg or 5)
    pts_by_amount = net * float(settings.points_per_currency_unit or 1)
    points = max(int(pts_by_weight), int(pts_by_amount))

    if points <= 0:
        return

    expiry = add_days(today(), int(settings.points_expiry_days or 90))
    _add_transaction(
        customer=order.customer,
        transaction_type="Credit",
        points=points,
        reference_doctype="Laundry Order",
        reference_name=order.name,
        expiry_date=expiry,
        notes=f"Earned on order {order.name}",
    )

    # Update account fields atomically
    acct_name = frappe.db.get_value("Loyalty Account", {"customer": order.customer}, "name")
    if not acct_name:
        return

    acct = frappe.get_doc("Loyalty Account", acct_name)

    # Capture previous_order_date BEFORE overwriting last_order_date
    acct.previous_order_date = acct.last_order_date
    acct.last_order_date = getdate(today())
    acct.order_count = (acct.order_count or 0) + 1
    acct.total_points_earned = (acct.total_points_earned or 0) + points

    # Tier upgrade check
    acct.tier = _get_tier(acct.total_points_earned, settings)
    acct.tier_updated_on = today()

    # Streak
    streak_msg = _check_streak(acct, points, settings)
    if streak_msg:
        order.db_set("streak_progress_text", streak_msg)

    acct.save(ignore_permissions=True)
    _update_balance(order.customer)

    # Referral bonus — only on first order
    if acct.order_count == 1:
        customer = frappe.get_doc("Laundry Customer", order.customer)
        if customer.referred_by:
            _award_referral_bonus(customer, customer.referred_by, settings)


def maybe_issue_scratch_card(order):
    """Issue a scratch card when order_count hits the trigger frequency."""
    settings = frappe.get_cached_doc("Spinly Settings")
    trigger = int(settings.scratch_card_trigger_orders or 5)

    order_count = frappe.db.get_value(
        "Loyalty Account", {"customer": order.customer}, "order_count"
    ) or 0

    if order_count <= 0 or order_count % trigger != 0:
        return

    prize_type, prize_value = _roll_scratch_card()
    sc = frappe.new_doc("Scratch Card")
    sc.customer = order.customer
    sc.order = order.name
    sc.prize_type = prize_type
    sc.prize_value = prize_value
    sc.issued_on = today()
    sc.expiry_date = add_days(today(), 30)
    sc.insert(ignore_permissions=True)


def expire_points():
    """Daily job: expire Credit transactions past their expiry date."""
    expired = frappe.db.get_all(
        "Loyalty Transaction",
        filters={
            "transaction_type": "Credit",
            "has_been_expired": 0,
            "expiry_date": ["<", today()],
        },
        fields=["name", "customer", "points"],
    )
    for row in expired:
        _add_transaction(
            customer=row.customer,
            transaction_type="Expire",
            points=row.points,
            notes="Auto-expired",
        )
        frappe.db.set_value("Loyalty Transaction", row.name, "has_been_expired", 1)
        _update_balance(row.customer)


def recalculate_all_tiers():
    """Monthly job: recompute tier for all active accounts from total_points_earned."""
    settings = frappe.get_cached_doc("Spinly Settings")
    accounts = frappe.get_all(
        "Loyalty Account",
        filters={"is_active": 1},
        fields=["name", "total_points_earned"],
    )
    for acc in accounts:
        new_tier = _get_tier(acc.total_points_earned or 0, settings)
        frappe.db.set_value("Loyalty Account", acc.name, {
            "tier": new_tier,
            "tier_updated_on": today(),
        })


# Alias retained for backwards compatibility with any manual calls
recalculate_tiers = recalculate_all_tiers


def evaluate_streaks():
    """Weekly job: re-evaluate current_streak_weeks for all active accounts.
    Corrects any drift where real-time streak check (in earn_points) drifted.
    Does not create transactions — only corrects the counter.
    A streak is considered broken if no order was placed in the past 7 days."""
    accounts = frappe.get_all(
        "Loyalty Account",
        filters={"is_active": 1},
        fields=["name", "customer", "last_order_date", "current_streak_weeks"],
    )
    today_date = getdate(today())
    for acc in accounts:
        if not acc.last_order_date:
            if acc.current_streak_weeks != 0:
                frappe.db.set_value("Loyalty Account", acc.name, "current_streak_weeks", 0)
            continue
        days_since = (today_date - getdate(acc.last_order_date)).days
        # If no order in more than 7 days, streak should be 0 (broken)
        if days_since > 7 and acc.current_streak_weeks > 0:
            frappe.db.set_value("Loyalty Account", acc.name, "current_streak_weeks", 0)


# ── Promo engine ──────────────────────────────────────────────────────────────

def _apply_best_discount(doc):
    """
    Find the highest-priority active campaign that applies to this order.
    Sets doc.applied_promo + doc.promo_discount_amount.
    Does NOT touch discount_amount (that's computed in _apply_pricing).
    """
    today_date = getdate(today())
    promos = frappe.get_all(
        "Promo Campaign",
        filters={
            "is_active": 1,
            "start_date": ["<=", today_date],
            "end_date": [">=", today_date],
        },
        fields=["name", "campaign_type", "discount_pct", "min_weight_kg",
                "applicable_service", "priority", "max_uses", "usage_count"],
        order_by="priority desc",
    )

    if not promos:
        return

    customer = frappe.get_doc("Laundry Customer", doc.customer)
    eligible = []

    for p in promos:
        if p.max_uses and (p.usage_count or 0) >= p.max_uses:
            continue
        ctype = p.campaign_type
        if ctype == "Flash Sale":
            if not p.applicable_service or p.applicable_service == doc.service:
                eligible.append(p)
        elif ctype == "Weight Milestone":
            if (doc.total_weight_kg or 0) >= (p.min_weight_kg or 0):
                eligible.append(p)
        elif ctype == "Birthday":
            if customer.dob:
                if getdate(customer.dob).month == today_date.month:
                    eligible.append(p)
        # Win-Back and Referral are handled by background jobs, not order-level

    if not eligible:
        return

    # Highest priority wins (promos already sorted desc, take first eligible)
    best = eligible[0]
    subtotal = doc.subtotal or 0
    disc = round(subtotal * (best.discount_pct or 0) / 100, 2)
    doc.applied_promo = best.name
    doc.promo_discount_amount = disc

    # Increment usage count
    frappe.db.set_value("Promo Campaign", best.name, "usage_count",
                        (best.usage_count or 0) + 1)


# ── Private helpers ───────────────────────────────────────────────────────────

def _check_streak(acct, points_this_order: int, settings) -> str:
    """
    Update streak counter. Returns a user-facing progress message.
    Awards double-points bonus if streak target is reached.
    """
    weeks_required = int(settings.streak_weeks_required or 4)
    prev = acct.previous_order_date
    streak = acct.current_streak_weeks or 0

    if prev:
        days_gap = (getdate(today()) - getdate(prev)).days
        if days_gap <= 7:
            streak += 1
        else:
            streak = 1  # broken streak — restart
    else:
        streak = 1  # first order

    acct.current_streak_weeks = streak

    if streak >= weeks_required:
        # Double-points bonus
        _add_transaction(
            customer=acct.customer,
            transaction_type="Credit",
            points=points_this_order,
            notes=f"Streak bonus — {weeks_required}-week streak completed",
        )
        acct.total_points_earned = (acct.total_points_earned or 0) + points_this_order
        acct.current_streak_weeks = 0
        return "Streak complete! Double points awarded! 🎉"
    else:
        remaining = weeks_required - streak
        return f"{streak}/{weeks_required} weeks — {remaining} more for double points!"


def _award_referral_bonus(new_customer_doc, referrer_name: str, settings):
    """Credit referral bonus points to both new customer and referrer."""
    # Find an active Referral promo campaign for the bonus amount
    referral_promo = frappe.db.get_value(
        "Promo Campaign",
        {"campaign_type": "Referral", "is_active": 1},
        ["name", "referral_bonus_points"],
        as_dict=True,
    )
    bonus = (referral_promo.referral_bonus_points if referral_promo else 50) or 50

    _ensure_loyalty_account(new_customer_doc.name)
    _ensure_loyalty_account(referrer_name)

    for cust in [new_customer_doc.name, referrer_name]:
        _add_transaction(
            customer=cust,
            transaction_type="Credit",
            points=bonus,
            notes=f"Referral bonus — {new_customer_doc.full_name} joined",
        )
        _update_balance(cust)


def _ensure_loyalty_account(customer):
    if not frappe.db.exists("Loyalty Account", {"customer": customer}):
        la = frappe.new_doc("Loyalty Account")
        la.customer = customer
        la.insert(ignore_permissions=True)


def _add_transaction(customer, transaction_type, points, reference_doctype=None,
                     reference_name=None, expiry_date=None, notes=None):
    lt = frappe.new_doc("Loyalty Transaction")
    lt.customer = customer
    lt.transaction_type = transaction_type
    lt.points = points
    lt.reference_doctype = reference_doctype
    lt.reference_name = reference_name
    lt.expiry_date = expiry_date
    lt.notes = notes
    lt.insert(ignore_permissions=True)


def _update_balance(customer):
    credited = frappe.db.sql(
        "SELECT COALESCE(SUM(points),0) FROM `tabLoyalty Transaction` "
        "WHERE customer=%s AND transaction_type='Credit'",
        customer,
    )[0][0]
    debited = frappe.db.sql(
        "SELECT COALESCE(SUM(points),0) FROM `tabLoyalty Transaction` "
        "WHERE customer=%s AND transaction_type IN ('Debit','Expire')",
        customer,
    )[0][0]
    balance = max(0, int(credited) - int(debited))
    frappe.db.set_value(
        "Loyalty Account",
        {"customer": customer},
        {
            "current_balance": balance,
            "total_points_redeemed": int(debited),
        },
    )


def _get_tier(total_earned: int, settings=None) -> str:
    if settings is None:
        settings = frappe.get_cached_doc("Spinly Settings")
    silver = int(settings.tier_silver_pts or 500)
    gold = int(settings.tier_gold_pts or 2000)
    if total_earned >= gold:
        return "Gold"
    elif total_earned >= silver:
        return "Silver"
    return "Bronze"


def _roll_scratch_card() -> tuple:
    """Weighted random prize: No Prize 40%, Discount 35%, Bonus Pts 20%, Free Bag 5%."""
    prizes = [
        ("No Prize", 40, 0),
        ("Percentage Discount", 35, 10),
        ("Bonus Points", 20, 50),
        ("Free Bag", 5, 1),
    ]
    roll = random.randint(1, 100)
    cumulative = 0
    for prize_type, weight, value in prizes:
        cumulative += weight
        if roll <= cumulative:
            return prize_type, value
    return "No Prize", 0
