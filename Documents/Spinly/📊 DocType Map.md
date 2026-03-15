---
tags: [doctype, erd, schema, reference]
module: Root
type: reference
status: spec-approved
linked_doctypes: [Laundry Customer, Laundry Order, Laundry Job Card, Loyalty Account, Loyalty Transaction, Promo Campaign, Scratch Card, Laundry Machine, Laundry Consumable, Laundry Service, Garment Type, Alert Tag, Payment Method, WhatsApp Message Template, Language, Consumable Category, Spinly Settings, WhatsApp Message Log, Inventory Restock Log, Order Item, Order Alert Tag]
---

# 📊 DocType Map

All 21 DocTypes + 2 child tables in Spinly. Every DocType is managed by Frappe's schema engine — no manual SQL migrations required.

---

## Complete ER Diagram

```mermaid
erDiagram
    LAUNDRY_CUSTOMER {
        string name PK "CUST-.#####"
        string phone UK "unique, primary search"
        string full_name
        date dob
        string language_preference FK "→ Language"
        string referred_by FK "→ Laundry Customer (self)"
    }

    LOYALTY_ACCOUNT {
        string name PK "LACCT-.#####"
        string customer FK "→ Laundry Customer (unique)"
        int total_points "redeemable balance"
        int lifetime_points "never decrements"
        string tier "Bronze/Silver/Gold"
        date last_order_date
        date previous_order_date "for streak calc"
        int current_streak_weeks
        int order_count "for scratch card"
    }

    LOYALTY_TRANSACTION {
        string name PK "LTXN-.YYYY.-.#####"
        string loyalty_account FK "→ Loyalty Account"
        string order FK "→ Laundry Order"
        string transaction_type "Earn/Redeem/Expire/Bonus/Referral"
        int points
        date expiry_date
        string description
    }

    LAUNDRY_ORDER {
        string name PK "ORD-.YYYY.-.#####"
        string customer FK "→ Laundry Customer"
        date order_date
        string service FK "→ Laundry Service"
        string machine FK "→ Laundry Machine"
        float total_weight_kg
        float total_amount
        float discount_amount
        float net_amount "total - discount"
        string applied_promo FK "→ Promo Campaign"
        int loyalty_points_redeemed
        string payment_status "Unpaid/Paid"
        string payment_method FK "→ Payment Method"
        datetime eta
        string lot_number "LOT-YYYY-#####"
        string customer_comments
        string streak_progress_text
    }

    ORDER_ITEM {
        string name PK
        string parent FK "→ Laundry Order"
        string garment_type FK "→ Garment Type"
        string item_icon "fetched, display only"
        int quantity
        float weight_kg
        float unit_price
        float line_total
    }

    ORDER_ALERT_TAG {
        string name PK
        string parent FK "→ Laundry Order"
        string alert_tag FK "→ Alert Tag"
        string tag_name "fetched"
        string color_code "fetched"
        string icon_emoji "fetched"
    }

    LAUNDRY_JOB_CARD {
        string name PK "JOB-.YYYY.-.#####"
        string order FK "→ Laundry Order"
        string machine FK "→ Laundry Machine"
        string lot_number
        string customer_tier_badge "Bronze/Silver/Gold"
        string workflow_state "Sorting→...→Delivered"
        string special_instructions
        datetime machine_countdown_end
    }

    LAUNDRY_MACHINE {
        string name PK "MAC-.##"
        string machine_name
        float capacity_kg
        string status "Idle/Running/Maintenance Required/Out of Order"
        float current_load_kg
        datetime countdown_timer_end
        string maintenance_notes
    }

    LAUNDRY_SERVICE {
        string name PK "SRV-.###"
        string service_name
        string service_type "Wash & Fold/Wash & Iron/Dry Clean"
        float base_price_per_kg
        int processing_minutes
    }

    GARMENT_TYPE {
        string name PK "GT-.##"
        string garment_name
        string icon_emoji
        float default_weight_kg
        int sort_order
        int is_active
    }

    ALERT_TAG {
        string name PK "ATAG-.##"
        string tag_name
        string color_code "hex"
        string icon_emoji
        int sort_order
        int is_active
    }

    PAYMENT_METHOD {
        string name PK "PMETH-.##"
        string method_name
        int show_upi_qr "Yes/No"
        int sort_order
        int is_active
    }

    LANGUAGE {
        string name PK "LANG-.##"
        string language_name
        string language_code
        int is_active
    }

    WHATSAPP_MESSAGE_TEMPLATE {
        string name PK "WTPL-.##"
        string template_name
        string message_type
        string language FK "→ Language"
        string template_body
        int is_active
    }

    CONSUMABLE_CATEGORY {
        string name PK "CCAT-.##"
        string category_name
        string unit "ml/gm/pcs"
        int is_active
    }

    LAUNDRY_CONSUMABLE {
        string name PK "CONS-.###"
        string item_name
        string category FK "→ Consumable Category"
        float current_stock
        float reorder_threshold
        float reorder_quantity
        float consumption_per_kg
    }

    PROMO_CAMPAIGN {
        string name PK "PROMO-.###"
        string campaign_type "Flash Sale/Weight Milestone/Win-Back/Birthday/Referral"
        string discount_type "Percentage/Fixed/Free Service"
        float discount_value
        int priority
        date active_from
        date active_to
        float min_weight_kg
        string applies_to_service FK "→ Laundry Service (optional)"
        int win_back_days
        int referral_bonus_points
        int is_active
    }

    SCRATCH_CARD {
        string name PK "SCARD-.YYYY.-.#####"
        string customer FK "→ Laundry Customer"
        string order FK "→ Laundry Order"
        string prize_type "Percentage Discount/Free Bag/Bonus Points/No Prize"
        float prize_value
        string status "Pending/Scratched"
        int issued_via_whatsapp
        datetime scratched_at
    }

    WHATSAPP_MESSAGE_LOG {
        string name PK "WLOG-.YYYY.-.#####"
        string recipient_phone
        string customer FK "→ Laundry Customer"
        string message_type
        string template_used FK "→ WhatsApp Message Template"
        string order FK "→ Laundry Order (optional)"
        string status "Queued/Sent/Failed"
        datetime sent_at
        string error_message
    }

    INVENTORY_RESTOCK_LOG {
        string name PK "RSTOCK-.YYYY.-.#####"
        string consumable FK "→ Laundry Consumable"
        float quantity_added
        string restocked_by
        date restock_date
        string notes
    }

    SPINLY_SETTINGS {
        string name PK "Spinly Settings (Single)"
        time shift_start
        int shift_duration_hrs
        string upi_id
        string whatsapp_provider
        string whatsapp_api_key
        string whatsapp_api_url
        int enable_loyalty_program
        float points_per_kg
        float points_per_currency_unit
        int points_expiry_days
        float redemption_rate
        int scratch_card_frequency
        int streak_weeks_required
        int tier_silver_pts
        int tier_gold_pts
        int tier_silver_discount_pct
        int tier_gold_discount_pct
        string default_language FK "→ Language"
    }

    LAUNDRY_CUSTOMER ||--o| LOYALTY_ACCOUNT : "has one"
    LAUNDRY_CUSTOMER ||--o{ LOYALTY_TRANSACTION : "via account"
    LAUNDRY_CUSTOMER ||--o{ LAUNDRY_ORDER : "places"
    LAUNDRY_CUSTOMER ||--o{ SCRATCH_CARD : "receives"
    LAUNDRY_CUSTOMER ||--o{ WHATSAPP_MESSAGE_LOG : "receives"
    LAUNDRY_CUSTOMER }o--o| LAUNDRY_CUSTOMER : "referred_by"
    LAUNDRY_CUSTOMER }o--|| LANGUAGE : "prefers"

    LOYALTY_ACCOUNT ||--o{ LOYALTY_TRANSACTION : "ledger"
    LOYALTY_TRANSACTION }o--o| LAUNDRY_ORDER : "from order"

    LAUNDRY_ORDER ||--o{ ORDER_ITEM : "contains"
    LAUNDRY_ORDER ||--o{ ORDER_ALERT_TAG : "tagged with"
    LAUNDRY_ORDER ||--|| LAUNDRY_JOB_CARD : "generates"
    LAUNDRY_ORDER }o--|| LAUNDRY_SERVICE : "uses"
    LAUNDRY_ORDER }o--o| LAUNDRY_MACHINE : "assigned to"
    LAUNDRY_ORDER }o--o| PAYMENT_METHOD : "paid via"
    LAUNDRY_ORDER }o--o| PROMO_CAMPAIGN : "discounted by"

    LAUNDRY_JOB_CARD }o--o| LAUNDRY_MACHINE : "on machine"

    ORDER_ITEM }o--|| GARMENT_TYPE : "is type"
    ORDER_ALERT_TAG }o--|| ALERT_TAG : "is tag"

    PROMO_CAMPAIGN }o--o| LAUNDRY_SERVICE : "applies to"

    SCRATCH_CARD }o--|| LAUNDRY_ORDER : "from order"

    WHATSAPP_MESSAGE_LOG }o--o| LAUNDRY_ORDER : "about order"
    WHATSAPP_MESSAGE_LOG }o--|| WHATSAPP_MESSAGE_TEMPLATE : "uses template"
    WHATSAPP_MESSAGE_TEMPLATE }o--|| LANGUAGE : "in language"

    LAUNDRY_CONSUMABLE }o--|| CONSUMABLE_CATEGORY : "in category"
    INVENTORY_RESTOCK_LOG }o--|| LAUNDRY_CONSUMABLE : "restocks"

    SPINLY_SETTINGS }o--o| LANGUAGE : "default_language"
```

---

## DocType Summary Table

| DocType | Naming Series | Category | Module |
|---|---|---|---|
| Garment Type | `GT-.##` | Category Master | Config & Masters |
| Alert Tag | `ATAG-.##` | Category Master | Config & Masters |
| Payment Method | `PMETH-.##` | Category Master | Config & Masters |
| WhatsApp Message Template | `WTPL-.##` | Category Master | Notifications |
| Language | `LANG-.##` | Category Master | Config & Masters |
| Consumable Category | `CCAT-.##` | Category Master | Inventory |
| Laundry Service | `SRV-.###` | Configuration Master | Config & Masters |
| Laundry Machine | `MAC-.##` | Configuration Master | Config & Masters |
| Laundry Consumable | `CONS-.###` | Configuration Master | Inventory |
| Spinly Settings | `Single` | Configuration Master | Config & Masters |
| Laundry Customer | `CUST-.#####` | CRM Master | Order Flow |
| Laundry Order | `ORD-.YYYY.-.#####` | Transactional (Submittable) | Order Flow |
| Laundry Job Card | `JOB-.YYYY.-.#####` | Transactional (Submittable) | Order Flow |
| Loyalty Account | `LACCT-.#####` | Transactional | Loyalty |
| Loyalty Transaction | `LTXN-.YYYY.-.#####` | Transactional | Loyalty |
| Promo Campaign | `PROMO-.###` | Gamification | Loyalty |
| Scratch Card | `SCARD-.YYYY.-.#####` | Gamification | Loyalty |
| WhatsApp Message Log | `WLOG-.YYYY.-.#####` | Log / Audit | Notifications |
| Inventory Restock Log | `RSTOCK-.YYYY.-.#####` | Log / Audit | Inventory |
| Order Item | *(child of Laundry Order)* | Child Table | Order Flow |
| Order Alert Tag | *(child of Laundry Order)* | Child Table | Order Flow |

---

## Relationship Narrative

- **Laundry Customer** is the root entity. Every order, loyalty account, scratch card, and WhatsApp message traces back to a customer.
- **Loyalty Account** is 1-to-1 with Laundry Customer (unique constraint). It is the running ledger head; individual transactions are in **Loyalty Transaction**.
- **Laundry Order** is the primary transactional document. It links to Customer, Service, Machine, Payment Method, and a Promo Campaign. It has two child tables (Order Item, Order Alert Tag).
- **Laundry Job Card** is auto-created from Laundry Order on submit. 1-to-1 with an order.
- **Promo Campaign** is self-contained — it defines the rules. The discount result is stored only on `Laundry Order.discount_amount` (never in accounting).
- **Scratch Card** is created by the loyalty engine when `order_count % scratch_card_frequency == 0`.
- **WhatsApp Message Log** records every send attempt. In Phase 1 all entries are `Queued`.
- **Inventory Restock Log** auto-increments `Laundry Consumable.current_stock` on insert.

---

## Related
- [[🏠 Spinly — Master Index]]
- [[🔗 Hook Map]]
- [[01 - Order Flow/Data Model]]
- [[02 - Loyalty & Gamification/Data Model]]
- [[03 - Inventory/Data Model]]
- [[04 - Notifications/Data Model]]
- [[05 - Configuration & Masters/Data Model]]
