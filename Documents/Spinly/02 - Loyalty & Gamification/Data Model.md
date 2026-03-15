---
tags: [data-model, doctype, loyalty, gamification]
module: Loyalty & Gamification
type: data-model
status: spec-approved
linked_doctypes: [Loyalty Account, Loyalty Transaction, Promo Campaign, Scratch Card, Laundry Customer, Laundry Order, Laundry Service]
---

# Data Model — Loyalty & Gamification

Four DocTypes form the loyalty system. Two are transactional ledger records (Loyalty Account + Transaction), two are gamification tools (Promo Campaign + Scratch Card).

---

## ER Diagram

```mermaid
erDiagram
    LAUNDRY_CUSTOMER {
        string name PK "CUST-.#####"
        string phone
        date dob "for birthday promos"
        string referred_by FK "self-ref"
    }

    LOYALTY_ACCOUNT {
        string name PK "LACCT-.#####"
        string customer FK "unique constraint"
        int total_points "redeemable — decrements on redeem/expire"
        int lifetime_points "NEVER decrements — tier calculation only"
        string tier "Bronze/Silver/Gold"
        date last_order_date "updated on every earn"
        date previous_order_date "set to old last_order_date BEFORE overwriting"
        int current_streak_weeks "resets to 0 when streak completes or breaks"
        int order_count "used for every-5th scratch card"
    }

    LOYALTY_TRANSACTION {
        string name PK "LTXN-.YYYY.-.#####"
        string loyalty_account FK
        string order FK "optional"
        string transaction_type "Earn/Redeem/Expire/Bonus/Referral"
        int points
        date expiry_date "set on Earn transactions"
        string description
    }

    PROMO_CAMPAIGN {
        string name PK "PROMO-.###"
        string campaign_type "Flash Sale/Weight Milestone/Win-Back/Birthday/Referral"
        string discount_type "Percentage/Fixed/Free Service"
        float discount_value
        int priority "highest wins — no stacking"
        date active_from
        date active_to
        float min_weight_kg "Weight Milestone only"
        string applies_to_service FK "optional — blank = all services"
        int win_back_days "default 30"
        int referral_bonus_points "Referral type only"
        int is_active
    }

    SCRATCH_CARD {
        string name PK "SCARD-.YYYY.-.#####"
        string customer FK
        string order FK "the qualifying Nth order"
        string prize_type "Percentage Discount/Free Bag/Bonus Points/No Prize"
        float prize_value
        string status "Pending/Scratched"
        int issued_via_whatsapp "Yes/No"
        datetime scratched_at
    }

    LAUNDRY_SERVICE {
        string name PK "SRV-.###"
        string service_name
    }

    LAUNDRY_ORDER {
        string name PK
        float total_weight_kg
        float net_amount
        int loyalty_points_redeemed
        float discount_amount
    }

    LAUNDRY_CUSTOMER ||--o| LOYALTY_ACCOUNT : "has one (unique)"
    LOYALTY_ACCOUNT ||--o{ LOYALTY_TRANSACTION : "ledger entries"
    LOYALTY_TRANSACTION }o--o| LAUNDRY_ORDER : "from order"
    LAUNDRY_CUSTOMER ||--o{ SCRATCH_CARD : "receives"
    SCRATCH_CARD }o--|| LAUNDRY_ORDER : "qualifying order"
    PROMO_CAMPAIGN }o--o| LAUNDRY_SERVICE : "applies to (optional)"
    LAUNDRY_CUSTOMER }o--o| LAUNDRY_CUSTOMER : "referred_by (self-ref)"
```

---

## Loyalty Account — Field Reference

| Field | Type | Description |
|---|---|---|
| `name` | Data | Auto: `LACCT-.#####` |
| `customer` | Link → Laundry Customer | **Unique constraint** — guard via `frappe.db.exists()` before insert |
| `total_points` | Int | Current redeemable balance. **Decrements** on Redeem and Expire events. |
| `lifetime_points` | Int | Cumulative all-time earned points. **Never decrements.** Used exclusively for tier calculation. |
| `tier` | Select | `Bronze` / `Silver` / `Gold` — auto-updated on every earn |
| `last_order_date` | Date | Date of most recent order — **overwritten** on each earn |
| `previous_order_date` | Date | Set to old `last_order_date` **before** it is overwritten — used by `check_streak()` to avoid self-comparison |
| `current_streak_weeks` | Int | Consecutive weeks with ≥1 order. Resets to 0 on streak completion or gap. |
| `order_count` | Int | Total submitted orders. Used for `order_count % scratch_card_frequency` check. |

> **Critical distinction:** `total_points` can go down. `lifetime_points` only ever goes up. Tier is based on `lifetime_points` — customers cannot lose their tier by spending points.

---

## Loyalty Transaction — Field Reference

| Field | Type | Description |
|---|---|---|
| `name` | Data | Auto: `LTXN-.YYYY.-.#####` |
| `loyalty_account` | Link → Loyalty Account | The ledger this transaction belongs to |
| `order` | Link → Laundry Order | Optional — absent for Expire transactions |
| `transaction_type` | Select | `Earn` / `Redeem` / `Expire` / `Bonus` / `Referral` |
| `points` | Int | Positive for Earn/Bonus/Referral, negative for Redeem/Expire |
| `expiry_date` | Date | Set on Earn transactions (today + `points_expiry_days`). Null on others. |
| `description` | Small Text | Human-readable: "Earned 45 pts on ORD-2026-00012" |

---

## Promo Campaign — Field Reference

| Field | Type | Description |
|---|---|---|
| `name` | Data | Auto: `PROMO-.###` |
| `campaign_type` | Select | `Flash Sale` / `Weight Milestone` / `Win-Back` / `Birthday` / `Referral` |
| `discount_type` | Select | `Percentage` / `Fixed` / `Free Service` |
| `discount_value` | Float | % or ₹ amount depending on discount_type |
| `priority` | Int | Higher number = applied first when multiple campaigns eligible |
| `active_from` | Date | Campaign start date |
| `active_to` | Date | Campaign end date |
| `min_weight_kg` | Float | Weight Milestone only — minimum order weight |
| `applies_to_service` | Link → Laundry Service | Flash Sale only — blank = applies to all services |
| `win_back_days` | Int | Win-Back only — default 30 |
| `referral_bonus_points` | Int | Referral only — points credited to both referrer + referee |
| `is_active` | Check | Master on/off switch |

> **Priority Stack Rule:** Only the single highest-priority eligible campaign applies per order. No combining discounts. This keeps margin predictable.

---

## Scratch Card — Field Reference

| Field | Type | Description |
|---|---|---|
| `name` | Data | Auto: `SCARD-.YYYY.-.#####` |
| `customer` | Link → Laundry Customer | Who receives the scratch card |
| `order` | Link → Laundry Order | The qualifying order (the Nth order that triggered issuance) |
| `prize_type` | Select | `Percentage Discount` / `Free Bag` / `Bonus Points` / `No Prize` |
| `prize_value` | Float | % off or bonus points value |
| `status` | Select | `Pending` (issued, not yet scratched) / `Scratched` |
| `issued_via_whatsapp` | Check | Whether WhatsApp link was sent |
| `scratched_at` | Datetime | Timestamp when customer scratched |

---

## Related
- [[02 - Loyalty & Gamification/_Index]]
- [[02 - Loyalty & Gamification/Business Logic]]
- [[01 - Order Flow/Data Model]]
- [[📊 DocType Map]]
