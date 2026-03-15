# Spinly Laundry Management System — Design Specification

**Date:** 2026-03-15
**Version:** 1.0
**Status:** Approved for Implementation
**Framework:** Frappe Framework (Python / MariaDB / Jinja2)
**App Namespace:** `spinly`

---

## 1. Executive Summary

Spinly is a hyper-simplified, mobile-first laundry management system built as a custom Frappe app. Its core differentiator is a **low-click, icon-driven interface** for blue-collar staff alongside a full-featured manager dashboard. It automates ETA calculation, machine allocation, consumable inventory deduction, and customer loyalty — all without touching ERPNext's accounting module.

### Hard Constraints
- **No accounting:** Zero Journal Entries, GL Entries, or Payment Entries ever created. Payment is a binary `Paid / Unpaid` toggle only.
- **Low-click:** Every staff action for a **returning customer** is ≤ 5 taps from the POS home screen. New customer registration (name + phone entry) is a one-time exception, capped at 7 taps. Job Card advancement is 1 tap.
- **No coding to maintain:** All category data (garment types, alert tags, services, etc.) managed via Frappe Desk CRUD. No terminal access required post-launch.
- **Offline (Phase 2):** Phase 1 assumes stable WiFi. Offline queuing deferred.

---

## 2. Architecture

### 2.1 Approach: Frappe Pages + Client Scripts (Approach D)

| Layer | Technology | Maintained by |
|---|---|---|
| Staff POS UI | Single Frappe Page (HTML + CSS + vanilla JS) | Edit one `.html` file |
| Manager UI | Standard Frappe forms + Client Scripts | Browser-based form editor |
| Business Logic | Python (hooks, whitelisted API methods) | Python files |
| Print Formats | Jinja2 HTML templates | Browser-based template editor |
| Background Jobs | Redis / Python RQ | Frappe Scheduler |
| Database | MariaDB (via Frappe DocType system) | Auto-managed |

### 2.2 Two UI Surfaces

**Staff Surface (`/spinly-pos`):**
- Single-page Frappe Page: `spinly/page/spinly_pos/spinly_pos.html`
- Responsive: works on 10" tablets and 5" phones
- Thumb-zone layout: primary actions at bottom of screen
- Color system: Green = Done, Yellow = In Progress, Red = Alert/Action Required
- No npm, no webpack, no build toolchain

**Manager Surface (Frappe Desk):**
- Standard DocType list/form views
- Custom Workspace: "Spinly Dashboard" with KPI cards and quick links
- Client Scripts for UX enhancements (no separate frontend repo)

### 2.3 System Topology

```
Frappe Bench
├── spinly app
│   ├── /page/spinly_pos/      ← Staff POS (HTML/CSS/JS)
│   ├── /api/                  ← Whitelisted Python methods
│   ├── /logic/
│   │   ├── eta_calc.py        ← ETA engine
│   │   ├── inventory.py       ← Consumable deduction
│   │   ├── loyalty.py         ← Points, tiers, streaks, promos
│   │   ├── job_card.py        ← Job Card auto-creation from Order
│   │   └── machine.py         ← Machine countdown updates
│   ├── /integrations/
│   │   └── whatsapp_handler.py ← Stub (Phase 1), real provider (Phase 2)
│   └── hooks.py               ← All document event wiring
├── frappe (core)
├── erpnext (installed, not used for accounting)
└── MariaDB ← All DocType tables
    Redis   ← Background job queue
```

---

## 3. Data Model

### 3.1 Category Master DocTypes (6)
*All configurable via Frappe Desk CRUD — no developer needed to add/edit/deactivate.*

| DocType | Naming | Key Fields |
|---|---|---|
| **Garment Type** | `GT-.##` | `garment_name`, `icon_emoji`, `default_weight_kg`, `sort_order`, `is_active` |
| **Alert Tag** | `ATAG-.##` | `tag_name`, `color_code` (hex), `icon_emoji`, `sort_order`, `is_active` |
| **Payment Method** | `PMETH-.##` | `method_name`, `show_upi_qr` (Yes/No), `sort_order`, `is_active` |
| **WhatsApp Message Template** | `WTPL-.##` | `template_name`, `message_type`, `language` → Language, `template_body` (with `{{placeholders}}`), `is_active` |
| **Language** | `LANG-.##` | `language_name`, `language_code`, `is_active` |
| **Consumable Category** | `CCAT-.##` | `category_name`, `unit` (ml/gm/pcs), `is_active` |

**WhatsApp Template Placeholders:** `{{customer_name}}`, `{{eta}}`, `{{total_amount}}`, `{{upi_link}}`, `{{lot_number}}`, `{{points_balance}}`, `{{discount_applied}}`, `{{streak_progress}}`

**Message Types:** Order Confirmation, Pickup Reminder, Payment Thanks, Win-Back, Scratch Card, VIP Thank You

### 3.2 Configuration Master DocTypes (4)

| DocType | Naming | Key Fields |
|---|---|---|
| **Laundry Service** | `SRV-.###` | `service_name`, `service_type` (Wash & Fold / Wash & Iron / Dry Clean), `base_price_per_kg`, `processing_minutes` |
| **Laundry Machine** | `MAC-.##` | `machine_name`, `capacity_kg`, `status` (Idle/Running/Maintenance Required/Out of Order), `current_load_kg`, `countdown_timer_end`, `maintenance_notes` |
| **Laundry Consumable** | `CONS-.###` | `item_name`, `category` → Consumable Category, `current_stock`, `reorder_threshold`, `reorder_quantity`, `consumption_per_kg` |
| **Spinly Settings** | `Single` | See Section 3.6 |

### 3.3 CRM Master DocType (1)

**Laundry Customer** `CUST-.#####`
- `phone` (unique, primary search key)
- `full_name`
- `dob` (for birthday campaigns)
- `language_preference` → Language
- `referred_by` → Laundry Customer
- Auto-creates linked `Loyalty Account` on insert via `after_insert` hook

### 3.4 Transactional DocTypes (4)

**Laundry Order** `ORD-.YYYY.-.#####` *(Submittable)*
- `customer` → Laundry Customer
- `order_date`
- `service` → Laundry Service
- `machine` → Laundry Machine (set by ETA engine on `before_save`, displayed on POS Screen 3)
- `order_items` → child table (Order Item)
- `alert_tags` → child table (Order Alert Tag)
- `total_weight_kg`, `total_amount`, `discount_amount`
- `net_amount` (computed: `total_amount - discount_amount` — used for loyalty points calculation and invoice display)
- `applied_promo` → Promo Campaign
- `loyalty_points_redeemed`
- `payment_status` (Unpaid / Paid)
- `payment_method` → Payment Method
- `eta` (datetime, auto-calculated on `before_save`)
- `lot_number` (auto-generated, format: `LOT-YYYY-#####`)
- `customer_comments`
- `streak_progress_text` (e.g. "3/4 weeks — one more for double points!" or "Streak complete! Double points awarded!" on completion)

**Laundry Job Card** `JOB-.YYYY.-.#####` *(Submittable)*
- `order` → Laundry Order
- `machine` → Laundry Machine
- `lot_number` (fetched from order, displayed large)
- `customer_tier_badge` (Bronze / Silver / Gold — fetched from Loyalty Account)
- `workflow_state`: Sorting → Washing → Drying → Ironing → Ready → Delivered
- `special_instructions`
- `machine_countdown_end`

**Loyalty Account** `LACCT-.#####`
- `customer` → Laundry Customer (1-to-1, **unique constraint on `customer` field** — guard against duplicates via `frappe.db.exists()` before insert)
- `total_points` (current redeemable balance — decrements on redeem/expire)
- `lifetime_points` (never decrements — used for tier calculation)
- `tier` (Bronze / Silver / Gold — auto-updated)
- `last_order_date`
- `previous_order_date` (set to old `last_order_date` before overwriting — used for streak calculation to avoid self-comparison)
- `current_streak_weeks`
- `order_count` (total orders — used for scratch card every-5th logic)

**Loyalty Transaction** `LTXN-.YYYY.-.#####`
- `loyalty_account` → Loyalty Account
- `order` → Laundry Order
- `transaction_type` (Earn / Redeem / Expire / Bonus / Referral)
- `points`
- `expiry_date`
- `description`

### 3.5 Gamification DocTypes (2)

**Promo Campaign** `PROMO-.###`
- `campaign_type` (Flash Sale / Weight Milestone / Win-Back / Birthday / Referral)
- `discount_type` (Percentage / Fixed / Free Service)
- `discount_value`
- `priority` (integer — highest priority wins when multiple campaigns match)
- `active_from`, `active_to`
- `min_weight_kg` (for Weight Milestone type)
- `applies_to_service` → Laundry Service (optional — blank means all services)
- `win_back_days` (default 30, for Win-Back type)
- `referral_bonus_points` (for Referral type)
- `is_active`

**Scratch Card** `SCARD-.YYYY.-.#####`
- `customer` → Laundry Customer
- `order` → Laundry Order (the qualifying 5th order)
- `prize_type` (Percentage Discount / Free Bag / Bonus Points / No Prize)
- `prize_value`
- `status` (Pending / Scratched)
- `issued_via_whatsapp` (Yes/No)
- `scratched_at`

### 3.6 Spinly Settings (Single DocType)

**Shift:**
- `shift_start` (time), `shift_duration_hrs` (default 10)

**Payments:**
- `upi_id`

**WhatsApp:**
- `whatsapp_provider` (Stub / Twilio / Interakt / Wati)
- `whatsapp_api_key`, `whatsapp_api_url`

**Loyalty:**
- `enable_loyalty_program` (Yes/No)
- `points_per_kg`, `points_per_currency_unit`
- `points_expiry_days` (default 90)
- `redemption_rate` (e.g. 100 pts = ₹10)
- `scratch_card_frequency` (default 5)
- `streak_weeks_required` (default 4)
- `tier_silver_pts` (default 500), `tier_gold_pts` (default 2000)
- `tier_silver_discount_pct` (default 5), `tier_gold_discount_pct` (default 10)

**UI:**
- `default_language` → Language

### 3.7 Log / Audit DocTypes (2)

**WhatsApp Message Log** `WLOG-.YYYY.-.#####`
- `recipient_phone`, `customer` → Laundry Customer
- `message_type`, `template_used` → WhatsApp Message Template
- `order` → Laundry Order (optional)
- `status` (Queued / Sent / Failed)
- `sent_at`, `error_message`

**Inventory Restock Log** `RSTOCK-.YYYY.-.#####`
- `consumable` → Laundry Consumable
- `quantity_added`, `restocked_by`, `restock_date`, `notes`
- `after_insert` hook auto-increments `current_stock` on Laundry Consumable

### 3.8 Child DocTypes (2)

**Order Item** *(child of Laundry Order)*
- `garment_type` → Garment Type
- `item_icon` (fetched from Garment Type, display only)
- `quantity`, `weight_kg`, `unit_price`, `line_total`

**Order Alert Tag** *(child of Laundry Order)*
- `alert_tag` → Alert Tag
- `tag_name`, `color_code`, `icon_emoji` (fetched, display only)

### 3.9 Complete DocType Count

| Category | Count |
|---|---|
| Category Masters | 6 |
| Configuration Masters | 4 |
| CRM Master | 1 |
| Transactional | 4 |
| Gamification | 2 |
| Logs / Audit | 2 |
| Child Tables | 2 |
| **Total** | **21** |

---

## 4. Business Logic

### 4.1 ETA Calculation (`spinly/logic/eta_calc.py`)
Triggered: `Laundry Order → before_save`

```
1. Filter machines: status = Idle or Running, NOT Maintenance/Out of Order
2. For Silver/Gold tier customers: sort eligible machines by current_load_kg ASC
   (assigns least-loaded machine → lower queue time → earlier/lower ETA = priority benefit)
   For Bronze: sort by current_load_kg ASC as well (standard FIFO)
3. For each eligible machine m:
     if (m.current_load_kg + order.total_weight_kg) <= m.capacity_kg:
         T_queue = sum of remaining time for all active jobs on machine m
         T_service = order.service.processing_minutes
         ETA = now + T_queue + T_service
         if ETA > shift_end:
             overflow = ETA - shift_end
             ETA = next_day_shift_start + overflow
         assign machine → set order.machine = m.name, set order.eta = ETA, break
4. If no machine found: ETA = next available slot across all machines
```

### 4.2 Consumable Deduction (`spinly/logic/inventory.py`)
Triggered: `Laundry Job Card → on_submit`

```
For each active Laundry Consumable:
    deduction = order.total_weight_kg × consumable.consumption_per_kg
    new_stock = consumable.current_stock - deduction
    frappe.db.set_value("Laundry Consumable", consumable.name, "current_stock", new_stock)
    if new_stock < consumable.reorder_threshold:
        create low-stock alert notification for System Manager role
```

### 4.3 Loyalty Points Engine (`spinly/logic/loyalty.py`)
Triggered: `Laundry Order → on_submit`

```
earn_points():
    # Use net_amount (post-discount) for currency-based points
    points = max(
        order.total_weight_kg × settings.points_per_kg,
        order.net_amount × settings.points_per_currency_unit
    )
    create Loyalty Transaction (Earn, expiry = today + points_expiry_days)
    account.total_points += points
    account.lifetime_points += points
    account.order_count += 1
    # Capture previous date BEFORE overwriting — used by check_streak()
    account.previous_order_date = account.last_order_date
    account.last_order_date = today
    update_tier(account)
    check_streak(account, order)
    # Check referral bonus on first order only
    if account.order_count == 1 and customer.referred_by:
        award_referral_bonus(customer, customer.referred_by)

update_tier(account):
    if account.lifetime_points >= settings.tier_gold_pts: tier = Gold
    elif account.lifetime_points >= settings.tier_silver_pts: tier = Silver
    else: tier = Bronze

check_streak(account, order):
    # Compare against previous_order_date (captured before last_order_date was overwritten)
    days_since_last = (today - account.previous_order_date).days if account.previous_order_date else 999
    if days_since_last <= 7:
        account.current_streak_weeks += 1
    else:
        account.current_streak_weeks = 1
    streak = account.current_streak_weeks
    if streak >= settings.streak_weeks_required:
        # Award double points bonus
        create Loyalty Transaction (Bonus, points = points earned this order)
        account.total_points += points  # double the points just earned
        account.current_streak_weeks = 0
        order.streak_progress_text = "Streak complete! Double points awarded!"
    else:
        order.streak_progress_text = f"{streak}/{settings.streak_weeks_required} weeks — {settings.streak_weeks_required - streak} more for double points!"

award_referral_bonus(new_customer_doc, referrer_customer_name):
    # referrer_customer_name is the value of customer.referred_by (a Link field — e.g. "CUST-00042")
    referrer_account = frappe.db.get_value("Loyalty Account", {"customer": referrer_customer_name})
    referral_promo = get active Promo Campaign where campaign_type = "Referral"
    if referral_promo:
        bonus = referral_promo.referral_bonus_points
        # Credit new customer
        create Loyalty Transaction (Referral, bonus pts) for new_customer's account
        # Credit referrer
        create Loyalty Transaction (Referral, bonus pts) for referrer's account
```

### 4.4 Promo Campaign Engine (`spinly/logic/loyalty.py`)
Triggered: `Laundry Order → before_save`

```
apply_best_discount():
    active_promos = get all Promo Campaigns where is_active=1
                    and active_from <= today <= active_to
    eligible = []
    for promo in active_promos:
        if promo.campaign_type == "Flash Sale":
            if not promo.applies_to_service or promo.applies_to_service == order.service:
                eligible.append(promo)
        if promo.campaign_type == "Weight Milestone":
            if order.total_weight_kg >= promo.min_weight_kg:
                eligible.append(promo)
        if promo.campaign_type == "Birthday":
            if customer.dob.month == today.month:
                eligible.append(promo)
        # Win-Back and Referral handled by background jobs, not order-level
    if eligible:
        best = max(eligible, key=lambda p: p.priority)
        order.applied_promo = best.name
        order.discount_amount = calculate_discount(best, order.total_amount)
        # discount_amount only — no ledger entries, no credit notes
```

### 4.5 Scratch Card Engine
Triggered: `Laundry Job Card → on_update (workflow_state → Ready)`

**Ordering dependency:** `account.order_count` is incremented inside `earn_points()` which fires on `Laundry Order → on_submit`. The Job Card is created after order submit, and only reaches `Ready` state later — so `order_count` is always up-to-date before this check runs.

```
if account.order_count % settings.scratch_card_frequency == 0:
    create Scratch Card (status=Pending)
    queue WhatsApp message (type=Scratch Card)
```

### 4.6 Job Card Auto-Creation (`spinly/logic/job_card.py`)
Triggered: `Laundry Order → on_submit`

```
create_from_order(order):
    job_card = new Laundry Job Card
    job_card.order = order.name
    job_card.machine = order.machine          # copied from ETA engine assignment
    job_card.lot_number = order.lot_number
    job_card.special_instructions = order.customer_comments
    job_card.workflow_state = "Sorting"       # always starts at first step
    # Fetch tier badge from Loyalty Account
    account = frappe.db.get_value("Loyalty Account", {"customer": order.customer}, ["tier"])
    job_card.customer_tier_badge = account.tier if account else "Bronze"
    job_card.insert()
```

---

## 5. Complete Hook Map (`hooks.py`)

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
        # Guard inside on_payment_confirmed:
        #   if doc.payment_status == "Paid" and
        #      doc.get_doc_before_save().payment_status != "Paid":
        #       send_payment_thanks()
        # This ensures the WhatsApp fires only on the Unpaid→Paid transition,
        # not on every subsequent save of the order.
    },
    "Laundry Job Card": {
        "on_submit": "spinly.logic.inventory.deduct_consumables",
        "on_update": [
            "spinly.logic.machine.update_countdown",       # on workflow_state → Running
            "spinly.integrations.whatsapp_handler.send_pickup_reminder",  # on workflow_state → Ready
            "spinly.logic.loyalty.issue_scratch_card",    # on workflow_state → Ready
            # NOTE: streak is checked on Order submit (earn_points), NOT on Job Card delivery
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
    "weekly": [
        "spinly.logic.loyalty.evaluate_streaks"
    ],
    "monthly": [
        "spinly.logic.loyalty.recalculate_all_tiers"
    ]
}
```

---

## 6. UX Design

### 6.1 Staff POS Page (`/spinly-pos`)

**Screen 1 — Customer Search**
- Large numeric keypad for phone number entry
- On match: show customer name + tier badge (🥉🥈🥇)
- On no match: single [+ Add New] button (name + phone only)
- Gold/Silver customers get a visible priority indicator

**Screen 2 — Order Builder**
- Icon grid from Garment Type master (configurable, sorted by `sort_order`)
- `+` / `−` counters per item, OR a single weight input field
- 3 service buttons (from Laundry Service master)
- Alert tag toggles (from Alert Tag master, color-coded per `color_code`)

**Screen 3 — Confirm & Print**
- Summary: Order ID, Lot Number, Machine assigned, ETA
- Large alert badges (⚠️ WHITES etc.)
- Loyalty prompt if points available: "Apply X pts for ₹Y off?" → [YES] [NO]
- Active promo discount shown if applicable
- [✅ CONFIRM & PRINT] — submits order, triggers thermal Job Card print + A4 Invoice PDF

**Job Card Advancement Screen**
- Shows: Lot ID (large font), Machine #, Tier badge, Alert warnings
- Workflow progress bar: Sorting → Washing → Drying → Ironing → Ready → Delivered
- One massive [➡️ NEXT STEP] button (yellow while in progress, green when Ready)
- [💵 MARK AS PAID] button appears at Ready/Delivered stage

### 6.2 Manager Workspace ("Spinly Dashboard")
- Today's Orders count + revenue
- Low Stock Alerts (consumables below threshold, red highlight)
- Machine Status Board (color-coded: green=Idle, yellow=Running, red=Out of Order)
- Top 10 Customers leaderboard (by monthly spend)
- Pending Orders list
- Quick links: Inventory, Machines, Promos, Settings, WhatsApp Log

### 6.3 Color System (Universal)
| Color | Meaning | Used for |
|---|---|---|
| Green | Done / Go | Completed steps, Paid status, Idle machines |
| Yellow | In Progress | Current workflow step, Running machines |
| Red | Action Required | Alerts, Out of Order, Unpaid overdue |
| Blue | Info | ETA, tier badges |

### 6.4 Multi-lingual Support
- WhatsApp Message Templates stored per Language (from Language master)
- POS page sends `customer.language_preference` to API; response messages use matching template
- Staff UI language selectable from Login (maps to `default_language` in Settings)

---

## 7. Print Formats

### 7.1 Internal Job Tag (Thermal — 80mm)
Jinja2 template: `spinly/print_formats/job_tag.html`
- Lot ID in very large font (physical bag tag)
- Machine #
- Alert badges (⚠️ WHITES / ⚠️ HEAVY SOIL etc.) in bold
- Customer tier badge
- Step checklist (staff can physically tick)
- Customer comments / special instructions

### 7.2 Customer Invoice (A4 / PDF)
Jinja2 template: `spinly/print_formats/customer_invoice.html`
- Order number, date, customer name
- Item table (garment, qty, price)
- Total weight, service selected
- Discount applied (promo or loyalty)
- Grand total
- ETA (date + time)
- UPI QR code (generated from `upi_id` in Spinly Settings)
- Loyalty points earned this order + running balance
- Streak progress message

---

## 8. WhatsApp Integration

### 8.1 Architecture (`spinly/integrations/whatsapp_handler.py`)
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

### 8.2 Trigger Map
| Event | Message Type | Key Context Variables |
|---|---|---|
| Order submitted | Order Confirmation | lot_number, eta, total_amount, upi_link |
| Job Card → Ready | Pickup Reminder | lot_number, total_amount, upi_link |
| Payment marked Paid | Payment Thanks | customer_name, points_earned |
| Daily job (30+ days inactive) | Win-Back | discount_from_win_back_promo |
| Every 5th order (Job Card → Ready) | Scratch Card | scratch_card_link |
| Owner manual trigger (top 3) | VIP Thank You | customer_name |

---

## 9. Roles & Permissions

| Role | DocType Access | UI Surface |
|---|---|---|
| **Laundry Staff** | Laundry Order (Create/Read), Laundry Job Card (Read/Write workflow), Laundry Customer (Create/Read) | Redirected to `/spinly-pos` on login |
| **Laundry Manager** | All DocTypes (Read/Write), Spinly Settings (Read), No delete on transactional | Frappe Desk — full workspace |
| **System Manager** | Full access including Settings, Fixtures, Scheduler logs | Frappe Desk |

---

## 10. Mock Data Strategy

### 10.1 Fixtures (`spinly/fixtures/`)
Loaded via `bench migrate` — JSON files, no code.

**Categories (seed first):**
- 6 Garment Types: Shirt 👕, Pants 👖, Saree 👗, Bedding 🛏️, Jacket 🧥, Woolen 🧣
- 4 Alert Tags: Whites Only ⚪, Color Bleed Risk 🔴, Delicates 🪶, Heavy Soil 💪
- 3 Payment Methods: Cash, UPI, Card
- 3 Languages: English (en), Hindi (hi), Marathi (mr)
- 3 Services: Wash & Fold (45 min, ₹40/kg), Wash & Iron (60 min, ₹60/kg), Dry Clean (90 min, ₹120/kg)
- 4 Consumable Categories: Detergent, Softener, Stain Remover, Fabric Conditioner
- WhatsApp templates for all 6 message types in 3 languages = 18 templates

**Machines (5):**
| Machine | Capacity | Status | Purpose |
|---|---|---|---|
| MAC-01 Washer Alpha | 10 kg | Idle | Normal allocation |
| MAC-02 Washer Beta | 8 kg | Running | Queue time test |
| MAC-03 Washer Gamma | 12 kg | Idle | Heavy order test |
| MAC-04 Dryer Delta | 10 kg | Maintenance Required | Exclusion test |
| MAC-05 Washer Epsilon | 8 kg | Out of Order | Exclusion test |

**Inventory (6 consumables — 3 below threshold):**
- Detergent Pro: 4500 ml, threshold 500 ml ✅
- Fabric Softener: 380 ml, threshold 400 ml ⚠️ (below)
- Stain Remover: 1200 ml, threshold 200 ml ✅
- Whitener: 150 ml, threshold 200 ml ⚠️ (below)
- Conditioner Plus: 2000 ml, threshold 300 ml ✅
- Dry Clean Solvent: 800 ml, threshold 1000 ml ⚠️ (below)

**Customers (15):**
- 5 Bronze (new/infrequent)
- 5 Silver (500–2000 lifetime pts)
- 3 Gold (2000+ lifetime pts)
- 2 with birthday in current month (birthday promo test)
- 3 with `last_order_date` > 35 days ago (win-back test)
- 2 with referral relationships

**Orders (55 total):**
- 20 submitted/active — Job Cards in mixed workflow states
- 30 paid & delivered — historical data for leaderboard/analytics
- 5 drafts — for ETA validation testing
- Mix: all services, all garment types, all alert combinations
- 5 orders with loyalty points redeemed
- 3 orders with promo discounts applied
- 2 orders qualifying for scratch card (every-5th)

**Promo Campaigns (4 active):**
- Flash Sale: 20% off Dry Clean (active today)
- Weight Milestone: Free ironing on orders > 10 kg
- Win-Back: 15% off for customers inactive 30+ days
- Referral: 50 bonus points for referrer + referee

---

## 11. Testing Plan

### 11.1 No-Accounting Constraint Tests
| Test | Pass Condition |
|---|---|
| Submit 55 orders | Zero Journal Entries, GL Entries, Payment Entries in ERPNext |
| Mark 30 orders Paid | `payment_status` = Paid only. No ledger movement |
| Apply loyalty discount | Only `discount_amount` field on order updated. No credit note |
| Apply promo discount | Only `discount_amount` field updated |
| Check ERPNext Accounts module | Zero new entries after full test run |

### 11.2 Low-Click Tests
| Staff Action | Max Taps | Verification |
|---|---|---|
| New order for returning customer | ≤ 5 from POS home | Manual tap count |
| New order for new customer | ≤ 7 from POS home (one-time exception: name + phone entry) | Manual tap count |
| Advance Job Card one step | 1 tap | Single button render check |
| Mark order Paid | 1 tap | Payment toggle check |
| Mark machine Out of Order | 1 tap from machine list | Machine status button |
| Apply loyalty discount at checkout | 1 tap (Yes/No prompt) | POS confirm screen |

### 11.3 ETA Engine Tests
| Scenario | Expected Result |
|---|---|
| Machine at full capacity | System skips to next available machine |
| All machines full | ETA = next day shift start + overflow time |
| MAC-04 (Maintenance) | Excluded from allocation pool |
| MAC-05 (Out of Order) | Excluded from allocation pool |
| Silver tier customer | ETA lower (earlier) — assigned to least-loaded machine (priority benefit) |
| Gold tier customer | ETA lower (earlier) — assigned to least-loaded machine (priority benefit) |
| Order placed 30 min before shift end | ETA rolls to next day |
| Two simultaneous orders | No machine double-allocated |

### 11.4 Loyalty & Gamification Tests
| Test | Pass Condition |
|---|---|
| Submit order | Points earned = weight × rate (or amount × rate, whichever higher) |
| 5th order for customer | Scratch Card DocType created, WhatsApp Log entry queued |
| 4-week streak achieved | Double points Loyalty Transaction (Bonus) created when streak reaches 4 (streak_weeks_required = 4) |
| Redeem points at checkout | `loyalty_points_redeemed` set, `discount_amount` updated, Redeem transaction created |
| Points expiry (90 days) | Daily job creates Expire transactions, decrements `total_points` |
| Tier upgrade (Bronze→Silver) | `lifetime_points` crosses 500, tier auto-updates |
| Tier upgrade (Silver→Gold) | `lifetime_points` crosses 2000, tier auto-updates |
| Win-back daily job | Customer with `last_order_date` > 30 days gets WhatsApp Log entry |
| Birthday promo | Customer with birthday this month gets campaign applied on order |
| Referral bonus | Both customers receive Loyalty Transaction (Referral, 50 pts) |
| Priority stack | When Flash Sale + Weight Milestone both apply, only highest priority discounts |

### 11.5 WhatsApp Stub Tests
| Trigger | Expected WhatsApp Message Log Entry |
|---|---|
| Order submitted | status=Queued, type=Order Confirmation, correct phone |
| Job Card → Ready | status=Queued, type=Pickup Reminder, UPI link populated |
| Payment marked Paid | status=Queued, type=Payment Thanks |
| Win-back daily job | One entry per eligible customer (35+ days inactive) |
| Scratch card issued | status=Queued, type=Scratch Card |
| Owner VIP Thank You | Manual trigger from leaderboard, status=Queued |

### 11.6 Configurable Categories Tests
| Test | Pass Condition |
|---|---|
| Add new Garment Type | Appears on POS icon grid immediately (no code change) |
| Deactivate Alert Tag | Tag no longer shown on POS order builder |
| Add new Payment Method | Appears on POS checkout screen |
| Add WhatsApp template (new language) | New customer with that language receives template in their language |
| Add new Promo Campaign | Applies automatically to qualifying orders |

---

## 12. Sprint Plan (High-Level)

### Sprint 1 — Foundation (Days 1–4)
- `bench new-app spinly` + `bench install-app spinly`
- All 21 DocTypes + 2 child tables created
- Fixtures: categories, machines, inventory, services
- Roles and permissions configured
- Spinly Settings configured

### Sprint 2 — Core Order Flow (Days 5–9)
- ETA calculation engine
- Job Card auto-creation on order submit
- Consumable deduction on Job Card submit
- Staff POS page: Customer Search + Order Builder + Confirm screens
- Thermal Job Card print format
- A4 Customer Invoice print format

### Sprint 3 — WhatsApp & Payments (Days 10–12)
- `whatsapp_handler.py` stub
- All 6 WhatsApp trigger hooks wired
- WhatsApp Message Log DocType operational
- Payment status toggle on POS
- Inventory Restock Log + auto-increment

### Sprint 4 — Loyalty & Gamification (Days 13–17)
- Loyalty Account auto-creation
- Points engine (earn, redeem, expire)
- Tier system (Bronze/Silver/Gold)
- Streak bonus logic
- Scratch Card issuance
- Promo Campaign engine (all 5 types)
- Priority stack logic
- Loyalty prompt on POS checkout screen
- Tier badge on Job Card

### Sprint 5 — Manager Dashboard & Polish (Days 18–21)
- Spinly Dashboard workspace
- KPI cards (orders, revenue, low stock, machine status)
- Top 10 leaderboard
- Manual VIP Thank You trigger
- Multi-lingual WhatsApp template selection
- 55-record mock data load
- Full test run against all test cases

### Phase 2 (Future)
- Real WhatsApp provider integration (swap 3 lines in `whatsapp_handler.py`)
- Offline order queuing
- Driver Module (pickup/delivery routing)
- Customer self-service app
- Multi-store analytics

---

## 13. File Structure

```
spinly/
├── spinly/
│   ├── page/
│   │   └── spinly_pos/
│   │       ├── spinly_pos.html      ← Staff POS UI
│   │       ├── spinly_pos.css
│   │       └── spinly_pos.js
│   ├── logic/
│   │   ├── eta_calc.py
│   │   ├── inventory.py
│   │   ├── loyalty.py
│   │   └── job_card.py
│   ├── integrations/
│   │   └── whatsapp_handler.py
│   ├── api.py                       ← Whitelisted API methods for POS
│   ├── hooks.py
│   └── doctype/                     ← All 21 DocTypes
│       ├── laundry_customer/
│       ├── laundry_service/
│       ├── laundry_machine/
│       ├── laundry_consumable/
│       ├── spinly_settings/
│       ├── garment_type/
│       ├── alert_tag/
│       ├── payment_method/
│       ├── whatsapp_message_template/
│       ├── language/
│       ├── consumable_category/
│       ├── laundry_order/
│       ├── laundry_job_card/
│       ├── loyalty_account/
│       ├── loyalty_transaction/
│       ├── promo_campaign/
│       ├── scratch_card/
│       ├── whatsapp_message_log/
│       ├── inventory_restock_log/
│       ├── order_item/              ← child
│       └── order_alert_tag/         ← child
├── public/
│   └── print_formats/
│       ├── job_tag.html             ← Thermal 80mm
│       └── customer_invoice.html    ← A4 PDF
└── fixtures/
    ├── garment_type.json
    ├── alert_tag.json
    ├── payment_method.json
    ├── language.json
    ├── consumable_category.json
    ├── laundry_service.json
    ├── laundry_machine.json
    ├── laundry_consumable.json
    ├── whatsapp_message_template.json
    ├── spinly_settings.json
    ├── laundry_customer.json        ← 15 customers
    ├── loyalty_account.json
    ├── loyalty_transaction.json
    ├── laundry_order.json           ← 55 orders
    └── promo_campaign.json
```
