---
tags: [business-logic, loyalty, gamification, points, promos]
module: Loyalty & Gamification
type: business-logic
status: spec-approved
linked_doctypes: [Loyalty Account, Loyalty Transaction, Promo Campaign, Scratch Card, Laundry Customer, Laundry Order]
---

# Business Logic — Loyalty & Gamification

**File:** `spinly/logic/loyalty.py`

---

## earn_points() — Full Flow

**Triggered:** `Laundry Order → on_submit`

```mermaid
flowchart TD
    START([Laundry Order on_submit])
    GET_ACCT["Get Loyalty Account\nfor order.customer"]
    CALC_PTS["points = max(\n  total_weight_kg × points_per_kg,\n  net_amount × points_per_currency_unit\n)"]
    TXN["Create Loyalty Transaction\ntype=Earn\nexpiry=today + points_expiry_days"]
    UPDATE["account.total_points += points\naccount.lifetime_points += points\naccount.order_count += 1"]
    CAPTURE["account.previous_order_date = account.last_order_date\naccount.last_order_date = today"]
    TIER["update_tier(account)"]
    STREAK["check_streak(account, order)"]
    REF{"order_count == 1\nAND customer.referred_by?"}
    REFERRAL["award_referral_bonus()"]
    SAVE["account.save()"]
    DONE([Done])

    START --> GET_ACCT --> CALC_PTS --> TXN --> UPDATE --> CAPTURE --> TIER --> STREAK --> REF
    REF -->|Yes| REFERRAL --> SAVE --> DONE
    REF -->|No| SAVE --> DONE
```

---

## update_tier()

```python
def update_tier(account):
    settings = frappe.get_single("Spinly Settings")
    if account.lifetime_points >= settings.tier_gold_pts:
        account.tier = "Gold"
    elif account.lifetime_points >= settings.tier_silver_pts:
        account.tier = "Silver"
    else:
        account.tier = "Bronze"
```

| Threshold | Tier | Benefits |
|---|---|---|
| 0 – 499 lifetime pts | Bronze | Standard pricing |
| 500 – 1999 lifetime pts | Silver | Priority queue, 5% discount |
| 2000+ lifetime pts | Gold | Free pickup bag, 10% discount, dedicated WhatsApp |

> Tier is based on **lifetime_points** — customers never lose tier by spending redeemable points.

---

## check_streak()

```mermaid
flowchart TD
    START(["check_streak(account, order)"])
    PREV{"previous_order_date\nexists?"}
    CALC["days_since_last =\n(today - previous_order_date).days"]
    NO_PREV["days_since_last = 999"]
    CHECK{"days_since_last ≤ 7?"}
    INC["account.current_streak_weeks += 1"]
    RESET["account.current_streak_weeks = 1"]
    STREAK_MET{"streak ≥\nstreak_weeks_required?"}
    BONUS["Create Loyalty Transaction\ntype=Bonus\npoints = same as earned this order\naccount.total_points += points\naccount.current_streak_weeks = 0\norder.streak_progress_text = 'Streak complete! Double points awarded!'"]
    PROGRESS["order.streak_progress_text = \n'X/Y weeks — Z more for double points!'"]
    DONE([Done])

    START --> PREV
    PREV -->|Yes| CALC --> CHECK
    PREV -->|No| NO_PREV --> CHECK
    CHECK -->|Yes| INC --> STREAK_MET
    CHECK -->|No| RESET --> STREAK_MET
    STREAK_MET -->|Yes| BONUS --> DONE
    STREAK_MET -->|No| PROGRESS --> DONE
```

> `previous_order_date` is captured **before** `last_order_date` is overwritten. This prevents self-comparison on the same day.

---

## apply_best_discount() — Promo Engine

**Triggered:** `Laundry Order → before_save`

```mermaid
flowchart TD
    START([Laundry Order before_save])
    FETCH["Fetch all Promo Campaigns where:\nis_active=1\nactive_from ≤ today ≤ active_to"]
    LOOP["For each promo:"]
    FS{"campaign_type\n= Flash Sale?"}
    FS_CHECK{"applies_to_service blank\nOR matches order.service?"}
    WM{"campaign_type\n= Weight Milestone?"}
    WM_CHECK{"order.total_weight_kg\n≥ min_weight_kg?"}
    BD{"campaign_type\n= Birthday?"}
    BD_CHECK{"customer.dob.month\n= today.month?"}
    SKIP["Skip\n(Win-Back + Referral\nhandled by scheduler)"]
    ADD["eligible.append(promo)"]
    BEST["best = max(eligible, key=priority)"]
    APPLY["order.applied_promo = best.name\norder.discount_amount = calculate_discount(best, total_amount)"]
    NONE["No discount applied"]
    DONE([Done])

    START --> FETCH --> LOOP
    LOOP --> FS
    FS -->|Yes| FS_CHECK
    FS_CHECK -->|Yes| ADD
    FS_CHECK -->|No| LOOP
    FS -->|No| WM
    WM -->|Yes| WM_CHECK
    WM_CHECK -->|Yes| ADD
    WM_CHECK -->|No| LOOP
    WM -->|No| BD
    BD -->|Yes| BD_CHECK
    BD_CHECK -->|Yes| ADD
    BD_CHECK -->|No| LOOP
    BD -->|No| SKIP --> LOOP
    ADD --> LOOP
    LOOP -->|All checked| BEST
    BEST --> APPLY --> DONE
    LOOP -->|eligible empty| NONE --> DONE
```

**Campaign types handled at order level:**
- ✅ Flash Sale
- ✅ Weight Milestone
- ✅ Birthday

**Campaign types handled by background scheduler (NOT order-level):**
- ⚙️ Win-Back — daily job
- ⚙️ Referral — earn_points() first-order check

---

## award_referral_bonus()

**Triggered:** Inside `earn_points()` when `order_count == 1` AND `customer.referred_by` is set.

```mermaid
sequenceDiagram
    participant NE as earn_points()
    participant RC as Referral Promo Campaign
    participant NA as New Customer's Loyalty Account
    participant RA as Referrer's Loyalty Account

    NE->>RC: Get active Promo Campaign where campaign_type = "Referral"
    RC-->>NE: bonus = referral_bonus_points (e.g. 50)
    NE->>NA: Create Loyalty Transaction (Referral, +50 pts)
    NA-->>NE: New customer credited
    NE->>RA: Get Loyalty Account for referrer_phone
    NE->>RA: Create Loyalty Transaction (Referral, +50 pts)
    RA-->>NE: Referrer credited
```

- Only fires on the **first order** (order_count == 1)
- Requires an active Promo Campaign of type `Referral` to be configured
- Both accounts credited simultaneously

---

## issue_scratch_card()

**Triggered:** `Laundry Job Card → on_update` when `workflow_state → Ready`

```python
def issue_scratch_card(doc, method):
    if doc.workflow_state != "Ready":
        return
    order = frappe.get_doc("Laundry Order", doc.order)
    account = frappe.get_doc("Loyalty Account", {"customer": order.customer})
    settings = frappe.get_single("Spinly Settings")

    if account.order_count % settings.scratch_card_frequency == 0:
        prize = assign_random_prize()  # internal logic
        card = frappe.new_doc("Scratch Card")
        card.customer = order.customer
        card.order = order.name
        card.prize_type = prize.type
        card.prize_value = prize.value
        card.status = "Pending"
        card.insert()
        whatsapp_handler.send_message(
            customer=order.customer,
            message_type="Scratch Card",
            context={"scratch_card_link": get_scratch_card_url(card.name)}
        )
        card.issued_via_whatsapp = 1
        card.save()
```

> `order_count` is already incremented by `earn_points()` (fired on Order submit). By the time the Job Card reaches `Ready`, the count is always current.

---

## Scheduler Jobs

### expire_old_points() — Daily

```python
def expire_old_points():
    # Find Earn transactions past their expiry that haven't been expired yet
    expired_txns = frappe.get_all(
        "Loyalty Transaction",
        filters={"transaction_type": "Earn", "expiry_date": ["<", today]},
        fields=["name", "loyalty_account", "points"]
    )
    for txn in expired_txns:
        account = frappe.get_doc("Loyalty Account", txn.loyalty_account)
        # Create Expire transaction
        frappe.get_doc({
            "doctype": "Loyalty Transaction",
            "loyalty_account": txn.loyalty_account,
            "transaction_type": "Expire",
            "points": -txn.points,
            "description": f"Expired points from {txn.name}"
        }).insert()
        account.total_points = max(0, account.total_points - txn.points)
        account.save()
```

### evaluate_streaks() — Weekly
Re-evaluates streak status for all active customers (catch-all for edge cases).

### recalculate_all_tiers() — Monthly
Recalculates tier for all customers from `lifetime_points`. Guards against any drift from real-time tier updates.

---

## create_loyalty_account() — After Customer Insert

**Triggered:** `Laundry Customer → after_insert`

```python
def create_loyalty_account(doc, method):
    # Guard against duplicates
    if frappe.db.exists("Loyalty Account", {"customer": doc.name}):
        return
    frappe.get_doc({
        "doctype": "Loyalty Account",
        "customer": doc.name,
        "total_points": 0,
        "lifetime_points": 0,
        "tier": "Bronze",
        "order_count": 0,
        "current_streak_weeks": 0
    }).insert(ignore_permissions=True)
```

---

## Anti-Patterns

- ❌ Never apply two promos simultaneously — priority stack allows only one
- ❌ Never create a credit note or GL entry for a discount — `discount_amount` field on order only
- ❌ Never let `lifetime_points` decrement — it is append-only for tier accuracy
- ❌ Never check streak using `last_order_date` directly — always use `previous_order_date` (which was captured before the overwrite)
- ❌ Never create a separate customer app for loyalty — WhatsApp is the loyalty channel

---

## Related
- [[02 - Loyalty & Gamification/_Index]]
- [[02 - Loyalty & Gamification/Data Model]]
- [[04 - Notifications/Business Logic]]
- [[🔗 Hook Map]]
- [[06 - System/Background Jobs]]
