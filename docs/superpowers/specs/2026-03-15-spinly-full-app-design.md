# Spinly — Full App Design Specification

**Date:** 2026-03-15
**Status:** Approved for Implementation
**Framework:** Frappe Framework (Python / MariaDB / Jinja2)
**App Namespace:** `spinly`
**Implementation Option:** A — Sequential Sprint Execution (5 sprints, dependency order)

---

## 1. Executive Summary

Spinly is a hyper-simplified, mobile-first laundry management system built as a custom Frappe app. Its core differentiator is a low-click, icon-driven staff POS alongside a full-featured manager dashboard. It automates ETA calculation, machine allocation, consumable inventory deduction, and customer loyalty — all without touching ERPNext's accounting module.

**Hard Constraints (non-negotiable):**
- Zero ERPNext accounting entries: no Journal Entries, GL Entries, or Payment Entries — ever
- All staff actions for a returning customer ≤ 5 taps from POS home
- All post-launch configuration (garment types, promos, services) via Frappe Desk — no terminal access needed
- WhatsApp is the loyalty channel; no separate customer app
- Phase 1: requires stable WiFi (offline deferred to Phase 2)

---

## 2. Architecture

**Approach D: Frappe Pages + Client Scripts** — no npm, no webpack, no build toolchain.

### 2.1 System Topology

```
Frappe Bench
├── spinly (custom app)
│   ├── page/spinly_pos/       ← Staff POS (single HTML/CSS/JS file)
│   ├── logic/
│   │   ├── eta_calc.py        ← ETA engine + machine allocation
│   │   ├── inventory.py       ← Consumable deduction + restock
│   │   ├── loyalty.py         ← Points, tiers, streaks, promos, scratch cards
│   │   ├── job_card.py        ← Job Card auto-creation
│   │   └── machine.py         ← Machine countdown updates
│   ├── integrations/
│   │   └── whatsapp_handler.py  ← Phase 1 stub (logs to DB as Queued)
│   ├── api.py                 ← @frappe.whitelist() methods for POS
│   ├── hooks.py               ← All doc_events + scheduler_events
│   ├── doctype/               ← 21 DocTypes + 2 child tables
│   └── tests/                 ← Python unit tests per module
├── frappe (core)
└── erpnext (installed, NOT used for accounting)
```

### 2.2 UI Surfaces

**Staff POS (`/spinly-pos`):** Single Frappe Page — `spinly/page/spinly_pos/spinly_pos.html`. Responsive (10" tablets + 5" phones). Thumb-zone layout. Color system: Green=Done, Yellow=In Progress, Red=Alert.

**Manager Desk:** Standard Frappe DocType forms + Custom Workspace "Spinly Dashboard". Client Scripts for UX enhancements.

---

## 3. Data Model — 21 DocTypes + 2 Child Tables

### 3.1 Category Masters (6) — Sprint 1

All configurable via Frappe Desk CRUD; no developer needed to add/edit/deactivate.

| DocType | Naming | Key Fields |
|---|---|---|
| Garment Type | `GT-.##` | `garment_name`, `icon_emoji`, `default_weight_kg`, `sort_order`, `is_active` |
| Alert Tag | `ATAG-.##` | `tag_name`, `color_code` (hex), `icon_emoji`, `sort_order`, `is_active` |
| Payment Method | `PMETH-.##` | `method_name`, `show_upi_qr`, `sort_order`, `is_active` |
| WhatsApp Message Template | `WTPL-.##` | `template_name`, `message_type`, `language` → Language, `template_body`, `is_active` |
| Language | `LANG-.##` | `language_name`, `language_code`, `is_active` |
| Consumable Category | `CCAT-.##` | `category_name`, `unit` (ml/gm/pcs), `is_active` |

### 3.2 Configuration Masters (4) — Sprint 1

| DocType | Naming | Key Fields |
|---|---|---|
| Laundry Service | `SRV-.###` | `service_name`, `service_type`, `base_price_per_kg`, `processing_minutes` |
| Laundry Machine | `MAC-.##` | `machine_name`, `capacity_kg`, `status`, `current_load_kg`, `countdown_timer_end` |
| Laundry Consumable | `CONS-.###` | `item_name`, `category` → Consumable Category, `current_stock`, `reorder_threshold`, `reorder_quantity`, `consumption_per_kg` |
| Spinly Settings | `Single` | See Section 3.6 |

### 3.3 CRM Master (1) — Sprint 1

**Laundry Customer** `CUST-.#####`

| Field | Type | Notes |
|---|---|---|
| `phone` | Data | Unique — primary search key |
| `full_name` | Data | |
| `dob` | Date | Birthday campaign trigger |
| `language_preference` | Link → Language | |
| `referred_by` | Link → Laundry Customer | Self-referential |

Auto-creates a linked `Loyalty Account` on `after_insert`.

### 3.4 Transactional DocTypes (4) — Sprints 2 + 4

**Laundry Order** `ORD-.YYYY.-.#####` *(Submittable)*

Key fields: `customer`, `service`, `machine`, `order_items` (child), `alert_tags` (child), `total_weight_kg`, `total_amount`, `discount_amount`, `net_amount` (computed), `applied_promo`, `loyalty_points_redeemed`, `payment_status`, `payment_method`, `eta`, `lot_number`, `streak_progress_text`.

**Laundry Job Card** `JOB-.YYYY.-.#####` *(Submittable)*

Key fields: `order`, `machine`, `lot_number`, `customer_tier_badge`, `workflow_state` (Sorting→Washing→Drying→Ironing→Ready→Delivered), `special_instructions`, `machine_countdown_end`.

**Loyalty Account** `LACCT-.#####`

| Field | Type | Critical Rule |
|---|---|---|
| `customer` | Link → Laundry Customer | **Unique constraint** — guard via `frappe.db.exists()` |
| `total_points` | Int | Redeemable balance — **can decrement** |
| `lifetime_points` | Int | All-time earned — **NEVER decrements** |
| `tier` | Select Bronze/Silver/Gold | Based on `lifetime_points` only |
| `last_order_date` | Date | Overwritten on each earn. Also used by Win-Back daily scheduler to identify customers inactive 30+ days |
| `previous_order_date` | Date | Set to old `last_order_date` BEFORE overwrite — used by streak logic to avoid self-comparison |
| `current_streak_weeks` | Int | Set to 0 on streak completion; set to 1 on gap (current order starts a new streak) |
| `order_count` | Int | Used for scratch card every-Nth check |

**Loyalty Transaction** `LTXN-.YYYY.-.#####`

Fields: `loyalty_account`, `order` (optional), `transaction_type` (Earn/Redeem/Expire/Bonus/Referral), `points` (positive or negative), `expiry_date` (set on Earn only), `description`.

### 3.5 Gamification DocTypes (2) — Sprint 4

**Promo Campaign** `PROMO-.###`

Fields: `campaign_type` (Flash Sale/Weight Milestone/Win-Back/Birthday/Referral), `discount_type` (Percentage/Fixed/Free Service), `discount_value`, `priority` (int — highest wins), `active_from`, `active_to`, `min_weight_kg`, `applies_to_service`, `win_back_days` (default 30), `referral_bonus_points`, `is_active`.

**Priority Stack Rule:** Only the single highest-priority eligible campaign applies per order. No combining.

**Scratch Card** `SCARD-.YYYY.-.#####`

Fields: `customer`, `order`, `prize_type` (Percentage Discount/Free Bag/Bonus Points/No Prize), `prize_value`, `status` (Pending/Scratched), `issued_via_whatsapp`, `scratched_at`.

### 3.6 Log / Audit DocTypes (2) — Sprint 3

**WhatsApp Message Log** `WLOG-.YYYY.-.#####`: `recipient_phone`, `customer`, `message_type`, `template_used`, `order`, `status` (Queued/Sent/Failed), `sent_at`, `error_message`.

**Inventory Restock Log** `RSTOCK-.YYYY.-.#####`: `consumable`, `quantity_added`, `restocked_by`, `restock_date`, `notes`. `after_insert` auto-increments `current_stock`.

### 3.7 Child Tables (2) — Sprint 2

**Order Item** (child of Laundry Order): `garment_type`, `item_icon`, `quantity`, `weight_kg`, `unit_price`, `line_total`.

**Order Alert Tag** (child of Laundry Order): `alert_tag`, `tag_name`, `color_code`, `icon_emoji`.

### 3.8 Spinly Settings — Loyalty Section

```
enable_loyalty_program     (Yes/No)
points_per_kg              (default 10)
points_per_currency_unit   (default 0.5)
points_expiry_days         (default 90)
redemption_rate            (e.g. 100 pts = ₹10)
scratch_card_frequency     (default 5)
streak_weeks_required      (default 4)
tier_silver_pts            (default 500)
tier_gold_pts              (default 2000)
tier_silver_discount_pct   (default 5)
tier_gold_discount_pct     (default 10)
```

---

## 4. Business Logic

### 4.1 `loyalty.py` — Full Function Reference

#### `create_loyalty_account(doc, method)`
Trigger: `Laundry Customer.after_insert`
- Guard: `if frappe.db.exists("Loyalty Account", {"customer": doc.name}): return`
- Insert Bronze account with all counters at 0

#### `apply_best_discount(doc, method)`
Trigger: `Laundry Order.before_save`
- Fetch all active Promo Campaigns (`is_active=1`, `active_from ≤ today ≤ active_to`) in a **single query** (no loop queries)
- For each promo: check eligibility by type (Flash Sale: service match; Weight Milestone: kg threshold; Birthday: DOB month match)
- Win-Back and Referral: skip at order level — handled by scheduler and first-order hook respectively
- Apply `max(eligible, key=priority)` — set `order.applied_promo` and `order.discount_amount`
- `net_amount = total_amount - discount_amount`

#### `earn_points(doc, method)`
Trigger: `Laundry Order.on_submit`

Full flow:
1. Get Loyalty Account for `doc.customer`
2. `points = max(total_weight_kg × points_per_kg, net_amount × points_per_currency_unit)` — uses `net_amount` (post-discount)
3. Create Loyalty Transaction (Earn, expiry = today + `points_expiry_days`)
4. `account.total_points += points`, `account.lifetime_points += points`, `account.order_count += 1`
5. `account.previous_order_date = account.last_order_date` (capture BEFORE overwrite)
6. `account.last_order_date = today`
7. `update_tier(account)`
8. `check_streak(account, order)`
9. If `account.order_count == 1` AND `customer.referred_by`: `award_referral_bonus()`
10. `account.save()`

#### `update_tier(account)`
```python
if account.lifetime_points >= settings.tier_gold_pts: account.tier = "Gold"
elif account.lifetime_points >= settings.tier_silver_pts: account.tier = "Silver"
else: account.tier = "Bronze"
```

#### `check_streak(account, order)`
- `days_since_last = (today - account.previous_order_date).days if account.previous_order_date else 999`
- If ≤ 7 days: `account.current_streak_weeks += 1`; else: `account.current_streak_weeks = 1` (gap resets to 1 — the current order starts a new streak; NOT 0)
- If streak ≥ `streak_weeks_required`: create Bonus Loyalty Transaction (same points as this earn), `account.current_streak_weeks = 0` (completion resets to 0), set `order.streak_progress_text = "Streak complete! Double points awarded!"`
- Else: set progress text `"{streak}/{required} weeks — {remaining} more for double points!"`

#### `award_referral_bonus(new_customer_doc, referrer_customer_name)`
- `referrer_customer_name` is the value of `customer.referred_by` (a Link field — the Laundry Customer name, e.g. `CUST-00042`)
- Get active Promo Campaign where `campaign_type = "Referral"` — if none, skip silently
- Create Referral Loyalty Transaction for new customer (+`referral_bonus_points`)
- Get referrer Loyalty Account via `frappe.db.get_value("Loyalty Account", {"customer": referrer_customer_name})`
- Create Referral Loyalty Transaction for referrer (+`referral_bonus_points`)

#### `issue_scratch_card(doc, method)`
Trigger: `Laundry Job Card.on_update`
- Guard: `if doc.workflow_state != "Ready": return`
- `if account.order_count % settings.scratch_card_frequency == 0`: create Scratch Card (Pending), queue WhatsApp (Scratch Card type), set `issued_via_whatsapp = 1`

#### `expire_old_points()` — Daily scheduler
- Single query: all Earn transactions where `expiry_date < today` AND `has_been_expired = 0` (idempotency guard — prevents double-expiry on scheduler retry/restart)
- For each expired transaction: create Expire Loyalty Transaction (negative points), decrement `account.total_points` (floor: `max(0, total_points - points)`), set `has_been_expired = 1` on the Earn transaction
- Performance: collect all affected `loyalty_account` names from the query result, load each account once, save once — no per-transaction account re-fetches
- **Note:** `has_been_expired` (Check field, default 0) must be added to the Loyalty Transaction DocType

#### `evaluate_streaks()` — Weekly scheduler
Re-evaluates streak for all active customers (edge-case catch-all).

#### `recalculate_all_tiers()` — Monthly scheduler
Recalculates tier from `lifetime_points` for every Loyalty Account. Guards against drift.

### 4.2 `eta_calc.py`
Trigger: `Laundry Order.before_save`
- Filter machines: status = Idle or Running only (exclude Maintenance Required, Out of Order)
- Silver/Gold tier: assign least-loaded machine (priority queue benefit)
- Bronze: standard FIFO (also least-loaded, but no priority)
- Calculate ETA = now + T_queue + T_service; if ETA > shift_end, overflow to next day

### 4.3 `inventory.py`
- `deduct_consumables`: on Job Card submit — `frappe.db.set_value` per consumable (no loop DB queries: use `get_all` then batch set)
- `apply_restock`: on Inventory Restock Log insert — increment `current_stock`
- Low stock alert: create Frappe Notification for System Manager role if below threshold

### 4.4 `job_card.py`
Trigger: `Laundry Order.on_submit`
- Auto-create Job Card at `workflow_state = Sorting`
- Copy machine, lot_number, special_instructions from order
- Fetch `customer_tier_badge` from Loyalty Account via `frappe.db.get_value` (single field fetch, not full doc)

### 4.5 `machine.py`

#### `update_countdown(doc, method)`
Trigger: `Laundry Job Card.on_update`
- Guard: `if doc.workflow_state != "Running": return`
- Fetch `processing_minutes` from the order's service via `frappe.db.get_value`
- `frappe.db.set_value("Laundry Machine", doc.machine, "countdown_timer_end", now + processing_minutes)`
- Also sets `doc.machine_countdown_end` on the Job Card for display

### 4.6 `whatsapp_handler.py` — Phase 1 Stub
```python
def send_message(customer, message_type, context):
    template = get_template(message_type, customer.language_preference)
    message = render_template(template.template_body, context)
    provider = frappe.db.get_single_value("Spinly Settings", "whatsapp_provider")
    if provider == "Stub":
        log_message(customer, message_type, "Queued")  # Phase 1
    else:
        send_via_provider(provider, customer.phone, message)  # Phase 2
```
Phase 2 upgrade: swap 3 lines in this file. Zero other changes needed.

---

## 5. Hook Map (`hooks.py`)

```python
doc_events = {
    "Laundry Customer": {
        "after_insert": "spinly.logic.loyalty.create_loyalty_account"
    },
    "Laundry Order": {
        "before_save": [
            "spinly.logic.eta_calc.calculate",
            "spinly.logic.loyalty.apply_best_discount"
        ],
        "on_submit": [
            "spinly.logic.job_card.create_from_order",
            "spinly.logic.loyalty.earn_points",
            "spinly.integrations.whatsapp_handler.send_order_confirmation"
        ],
        "on_update": "spinly.integrations.whatsapp_handler.on_payment_confirmed"
        # Guard inside: fires only on Unpaid→Paid transition
    },
    "Laundry Job Card": {
        "on_submit": "spinly.logic.inventory.deduct_consumables",
        "on_update": [
            "spinly.logic.machine.update_countdown",
            "spinly.integrations.whatsapp_handler.send_pickup_reminder",
            "spinly.logic.loyalty.issue_scratch_card"
        ]
    },
    "Inventory Restock Log": {
        "after_insert": "spinly.logic.inventory.apply_restock"
    }
}

scheduler_events = {
    "daily": [
        "spinly.logic.loyalty.expire_old_points",
        "spinly.integrations.whatsapp_handler.send_win_back_messages"
    ],
    "weekly": ["spinly.logic.loyalty.evaluate_streaks"],
    "monthly": ["spinly.logic.loyalty.recalculate_all_tiers"]
}
```

---

## 6. Staff POS — Screen Flow

**Screen 1 — Customer Search:** Numeric keypad. On match: show name + tier badge (🥉🥈🥇). On no match: [+ Add New] (name + phone only — 7 taps max).

**Screen 2 — Order Builder:** Icon grid from Garment Type master. +/− counters or single weight input. 3 service buttons. Alert tag toggles (color-coded).

**Screen 3 — Confirm & Print:** Summary (Order ID, Lot, Machine, ETA). Loyalty prompt: "Apply X pts for ₹Y off?" [YES] [NO]. Active promo shown. [✅ CONFIRM & PRINT] — submits order, triggers Job Card print + Invoice PDF.

**Job Card Screen:** Lot ID (large), Machine#, Tier badge, Alert warnings. Workflow progress bar. One [➡️ NEXT STEP] button. [💵 MARK AS PAID] at Ready/Delivered.

---

## 7. WhatsApp Trigger Map

| Event | Message Type | Key Context |
|---|---|---|
| Order submitted | Order Confirmation | lot_number, eta, total_amount, upi_link |
| Job Card → Ready | Pickup Reminder | lot_number, total_amount, upi_link |
| Payment → Paid | Payment Thanks | customer_name, points_earned |
| Daily job (30+ days inactive) | Win-Back | discount_from_win_back_promo |
| Every Nth order (Job Card → Ready) | Scratch Card | scratch_card_link |
| Owner manual trigger | VIP Thank You | customer_name |

---

## 8. Critical Anti-Patterns

These are implementation guardrails — violations will cause bugs that are hard to trace.

- ❌ **Never** apply two promos simultaneously — priority stack, one winner only
- ❌ **Never** create a GL Entry, Journal Entry, or Payment Entry for any reason — `discount_amount` field on the order only
- ❌ **Never** decrement `lifetime_points` — it is append-only; tier is derived from it
- ❌ **Never** use `last_order_date` for streak calculation — always use `previous_order_date` (captured before the overwrite)
- ❌ **Never** build a customer-facing app — WhatsApp is the loyalty channel

---

## 9. Testing Plan

All tests in `spinly/tests/` using `frappe.tests.utils.FrappeTestCase`. Test data created in-test (no fixture dependency).

> Full per-test setup and assertions are in `Documents/Spinly/02 - Loyalty & Gamification/Testing.md`. The groups below map 1:1 to that document's named test cases.

### Points Engine (LY-01 – LY-05)
- Points = max(weight×rate, net_amount×rate) — both paths tested
- total_points and lifetime_points updated correctly
- order_count incremented
- Expiry date = today + points_expiry_days

### Tier System (TI-01 – TI-04)
- Bronze→Silver at 500 lifetime pts
- Silver→Gold at 2000 lifetime pts
- Tier stable when spending redeemable points (lifetime_points unchanged)
- Monthly recalculate_all_tiers corrects drift

### Streak Logic (SK-01 – SK-06)
- Increment on ≤7-day gap
- Reset on >7-day gap
- Progress text format verified
- Double-points Bonus transaction on completion
- First-order edge case (previous_order_date = None)

### Promo Campaigns (PR-01 – PR-10)
- Flash Sale: service match + wrong-service rejection
- Weight Milestone: above + below threshold
- Birthday: correct month + wrong month
- Priority stack (highest wins, lower ignored)
- Win-Back NOT applied at order level
- Inactive + expired campaigns excluded

### Scratch Cards (SC-01 – SC-05)
- 5th, 10th order trigger; 3rd does not
- Configurable frequency respected
- issued_via_whatsapp flag set

### Referral (RF-01 – RF-03)
- Both accounts credited on first order
- Second order: no bonus
- No active Referral campaign: no bonus

### Points Expiry (EX-01 – EX-03)
- Expired earn transactions → Expire transaction created + total_points decremented
- Future expiry untouched
- Floor at 0 (never negative)
- Idempotency: running daily job twice does not double-expire the same transactions

### Redemption (RD-01 – RD-02)
- discount_amount updated, Redeem transaction created, total_points decremented
- lifetime_points and tier unchanged

---

## 10. Fixtures (Mock Data)

Loaded via `bench migrate` from JSON files in `spinly/fixtures/`.

- 6 Garment Types, 4 Alert Tags, 3 Payment Methods, 3 Languages
- 3 Services (Wash & Fold 45min ₹40/kg, Wash & Iron 60min ₹60/kg, Dry Clean 90min ₹120/kg)
- 5 Machines (2 Idle, 1 Running, 1 Maintenance Required, 1 Out of Order)
- 6 Consumables (3 below reorder threshold)
- 15 Customers (5 Bronze, 5 Silver, 3 Gold, 2 birthday this month, 3 inactive 35+ days, 2 referral pairs)
- 55 Orders (20 active, 30 delivered, 5 drafts; 5 with points redeemed, 3 with promo discounts)
- 4 active Promo Campaigns (Flash Sale, Weight Milestone, Win-Back, Referral)
- 18 WhatsApp templates (6 message types × 3 languages)

---

## 11. Sprint Plan

| Sprint | Days | Deliverables |
|---|---|---|
| 1 — Foundation | 1–4 | `bench new-app spinly`, all 21 DocTypes, fixtures, roles, Spinly Settings |
| 2 — Core Order Flow | 5–9 | ETA engine, Job Card auto-creation, consumable deduction, Staff POS (3 screens), print formats |
| 3 — WhatsApp & Payments | 10–12 | whatsapp_handler stub, all 6 trigger hooks, payment toggle, Inventory Restock Log |
| 4 — Loyalty & Gamification | 13–17 | loyalty.py (all functions), 4 loyalty DocTypes, Promo Campaign engine, POS loyalty prompt, all 30+ tests |
| 5 — Dashboard & Polish | 18–21 | Spinly Dashboard workspace, KPI cards, leaderboard, VIP trigger, multilingual templates, full mock data load |

---

## 12. Roles & Permissions

| Role | Access | UI Surface |
|---|---|---|
| Laundry Staff | Laundry Order (Create/Read), Job Card (Read/Write workflow), Customer (Create/Read) | Redirected to `/spinly-pos` on login |
| Laundry Manager | All DocTypes (Read/Write), Settings (Read), no delete on transactional | Frappe Desk — full workspace |
| System Manager | Full access | Frappe Desk |

---

## 13. Phase 2 Boundary

| Feature | Phase 1 | Phase 2 |
|---|---|---|
| WhatsApp | Stub — logs to DB as Queued | Real provider (3-line swap in whatsapp_handler.py) |
| Offline | Not supported | Order queuing |
| Driver Module | Not included | Pickup/delivery routing |
| Customer App | Not included | Self-service app |
| Multi-store | Not included | Analytics |

---

*Source documents: BRD.md, SDD.md (Plans.md), Architecture.md, DocType Map.md, Hook Map.md, 01–06 module specs — all status: spec-approved.*
