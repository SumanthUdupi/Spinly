---
tags: [data-model, doctype, order-flow]
module: Order Flow
type: data-model
status: spec-approved
linked_doctypes: [Laundry Order, Laundry Job Card, Order Item, Order Alert Tag, Laundry Customer, Laundry Service, Laundry Machine, Payment Method, Promo Campaign, Garment Type, Alert Tag]
---

# Data Model — Order Flow

Four DocTypes define the order flow: Laundry Order (the bill), Laundry Job Card (the internal tracker), and two child tables for garment line items and alert tags.

---

## ER Diagram

```mermaid
erDiagram
    LAUNDRY_CUSTOMER {
        string name PK "CUST-.#####"
        string phone UK
        string full_name
    }

    LAUNDRY_ORDER {
        string name PK "ORD-.YYYY.-.#####"
        string customer FK
        date order_date
        string service FK
        string machine FK
        float total_weight_kg
        float total_amount
        float discount_amount
        float net_amount "total - discount (computed)"
        string applied_promo FK
        int loyalty_points_redeemed
        string payment_status "Unpaid/Paid"
        string payment_method FK
        datetime eta "auto-calculated"
        string lot_number "LOT-YYYY-#####"
        string customer_comments
        string streak_progress_text
    }

    ORDER_ITEM {
        string garment_type FK
        string item_icon "display only"
        int quantity
        float weight_kg
        float unit_price
        float line_total
    }

    ORDER_ALERT_TAG {
        string alert_tag FK
        string tag_name "fetched"
        string color_code "fetched (hex)"
        string icon_emoji "fetched"
    }

    LAUNDRY_JOB_CARD {
        string name PK "JOB-.YYYY.-.#####"
        string order FK
        string machine FK
        string lot_number
        string customer_tier_badge "Bronze/Silver/Gold"
        string workflow_state "Sorting→Washing→Drying→Ironing→Ready→Delivered"
        string special_instructions
        datetime machine_countdown_end
    }

    LAUNDRY_SERVICE {
        string name PK "SRV-.###"
        string service_name
        int processing_minutes
        float base_price_per_kg
    }

    LAUNDRY_MACHINE {
        string name PK "MAC-.##"
        string machine_name
        float capacity_kg
        string status
        float current_load_kg
    }

    PAYMENT_METHOD {
        string name PK "PMETH-.##"
        string method_name
        int show_upi_qr
    }

    PROMO_CAMPAIGN {
        string name PK "PROMO-.###"
        string campaign_type
        int priority
    }

    GARMENT_TYPE {
        string name PK "GT-.##"
        string garment_name
        string icon_emoji
    }

    ALERT_TAG {
        string name PK "ATAG-.##"
        string tag_name
        string color_code
        string icon_emoji
    }

    LAUNDRY_CUSTOMER ||--o{ LAUNDRY_ORDER : "places"
    LAUNDRY_ORDER ||--o{ ORDER_ITEM : "contains"
    LAUNDRY_ORDER ||--o{ ORDER_ALERT_TAG : "tagged with"
    LAUNDRY_ORDER ||--|| LAUNDRY_JOB_CARD : "generates"
    LAUNDRY_ORDER }o--|| LAUNDRY_SERVICE : "uses service"
    LAUNDRY_ORDER }o--o| LAUNDRY_MACHINE : "assigned machine"
    LAUNDRY_ORDER }o--o| PAYMENT_METHOD : "paid via"
    LAUNDRY_ORDER }o--o| PROMO_CAMPAIGN : "discounted by"
    ORDER_ITEM }o--|| GARMENT_TYPE : "is type"
    ORDER_ALERT_TAG }o--|| ALERT_TAG : "is tag"
    LAUNDRY_JOB_CARD }o--o| LAUNDRY_MACHINE : "on machine"
```

---

## Laundry Order — Field Reference

| Field | Type | Description |
|---|---|---|
| `name` | Data | Auto: `ORD-.YYYY.-.#####` |
| `customer` | Link → Laundry Customer | Required |
| `order_date` | Date | Auto: today |
| `service` | Link → Laundry Service | Required (Wash & Fold / Wash & Iron / Dry Clean) |
| `machine` | Link → Laundry Machine | Set by ETA engine on `before_save` |
| `order_items` | Child Table → Order Item | One row per garment type |
| `alert_tags` | Child Table → Order Alert Tag | Warnings applied to this order |
| `total_weight_kg` | Float | Sum of order_items.weight_kg |
| `total_amount` | Currency | Sum of order_items.line_total |
| `discount_amount` | Currency | Set by promo engine or loyalty redemption |
| `net_amount` | Currency | **Computed:** `total_amount − discount_amount`. Used for loyalty points calc and invoice. |
| `applied_promo` | Link → Promo Campaign | Set by promo engine (single best promo) |
| `loyalty_points_redeemed` | Int | Points applied at checkout (POS Screen 3) |
| `payment_status` | Select | `Unpaid` / `Paid` |
| `payment_method` | Link → Payment Method | Cash / UPI / Card |
| `eta` | Datetime | Auto-calculated by ETA engine |
| `lot_number` | Data | Auto: `LOT-YYYY-#####` — displayed large on bag tag |
| `customer_comments` | Small Text | Copied to Job Card as `special_instructions` |
| `streak_progress_text` | Small Text | e.g. "3/4 weeks — 1 more for double points!" |

> **Submittable:** Once submitted, the order is locked. ETA, machine assignment, and discount are all frozen. Payment status can still be toggled post-submit.

---

## Laundry Job Card — Field Reference

| Field | Type | Description |
|---|---|---|
| `name` | Data | Auto: `JOB-.YYYY.-.#####` |
| `order` | Link → Laundry Order | The parent order |
| `machine` | Link → Laundry Machine | Copied from order on auto-creation |
| `lot_number` | Data | Copied from order — displayed in large font |
| `customer_tier_badge` | Select | Bronze / Silver / Gold — fetched from Loyalty Account at creation time |
| `workflow_state` | Select | `Sorting → Washing → Drying → Ironing → Ready → Delivered` |
| `special_instructions` | Small Text | Copied from order.customer_comments |
| `machine_countdown_end` | Datetime | Set by machine.update_countdown when Job Card hits Running |

> **Submittable:** Job Card submission triggers `inventory.deduct_consumables`.

---

## Order Item — Field Reference (Child Table)

| Field | Type | Description |
|---|---|---|
| `garment_type` | Link → Garment Type | e.g. Shirt, Saree, Bedding |
| `item_icon` | Data | Emoji fetched from Garment Type (display only) |
| `quantity` | Int | Count of items |
| `weight_kg` | Float | Weight for this line |
| `unit_price` | Currency | Price per kg from Laundry Service |
| `line_total` | Currency | Computed: `weight_kg × unit_price` |

---

## Order Alert Tag — Field Reference (Child Table)

| Field | Type | Description |
|---|---|---|
| `alert_tag` | Link → Alert Tag | e.g. Whites Only, Delicates |
| `tag_name` | Data | Fetched from Alert Tag (display only) |
| `color_code` | Data | Hex color fetched from Alert Tag |
| `icon_emoji` | Data | Emoji fetched from Alert Tag |

---

## Computed Fields

| Field | Formula | DocType |
|---|---|---|
| `net_amount` | `total_amount − discount_amount` | Laundry Order |
| `lot_number` | `LOT-YYYY-#####` (auto, like naming series) | Laundry Order |
| `customer_tier_badge` | Fetched from Loyalty Account at Job Card creation | Laundry Job Card |

---

## Naming Series

| DocType | Series | Example |
|---|---|---|
| Laundry Order | `ORD-.YYYY.-.#####` | `ORD-2026-00001` |
| Laundry Job Card | `JOB-.YYYY.-.#####` | `JOB-2026-00001` |
| Lot Number | `LOT-YYYY-#####` (custom field) | `LOT-2026-00001` |

---

## Related
- [[01 - Order Flow/_Index]]
- [[01 - Order Flow/Business Logic — ETA & Machine Allocation]]
- [[01 - Order Flow/Business Logic — Job Card Lifecycle]]
- [[05 - Configuration & Masters/Data Model]]
- [[📊 DocType Map]]
