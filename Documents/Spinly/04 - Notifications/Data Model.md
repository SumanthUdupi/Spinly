---
tags: [data-model, doctype, notifications, whatsapp]
module: Notifications
type: data-model
status: spec-approved
linked_doctypes: [WhatsApp Message Template, Language, WhatsApp Message Log, Laundry Customer, Laundry Order]
---

# Data Model — Notifications

Three DocTypes manage WhatsApp notifications: the Language master, the message template library, and the message log.

---

## ER Diagram

```mermaid
erDiagram
    LANGUAGE {
        string name PK "LANG-.##"
        string language_name "e.g. English"
        string language_code "e.g. en"
        int is_active
    }

    WHATSAPP_MESSAGE_TEMPLATE {
        string name PK "WTPL-.##"
        string template_name
        string message_type "Order Confirmation/Pickup Reminder/Payment Thanks/Win-Back/Scratch Card/VIP Thank You"
        string language FK "→ Language"
        string template_body "uses {{placeholders}}"
        int is_active
    }

    WHATSAPP_MESSAGE_LOG {
        string name PK "WLOG-.YYYY.-.#####"
        string recipient_phone
        string customer FK "→ Laundry Customer"
        string message_type
        string template_used FK "→ WhatsApp Message Template"
        string order FK "→ Laundry Order (optional)"
        string status "Queued / Sent / Failed"
        datetime sent_at
        string error_message
    }

    LAUNDRY_CUSTOMER {
        string name PK
        string phone
        string language_preference FK
    }

    LAUNDRY_ORDER {
        string name PK
    }

    LANGUAGE ||--o{ WHATSAPP_MESSAGE_TEMPLATE : "in language"
    WHATSAPP_MESSAGE_TEMPLATE ||--o{ WHATSAPP_MESSAGE_LOG : "used in"
    LAUNDRY_CUSTOMER ||--o{ WHATSAPP_MESSAGE_LOG : "receives"
    LAUNDRY_ORDER ||--o{ WHATSAPP_MESSAGE_LOG : "about order"
    LAUNDRY_CUSTOMER }o--|| LANGUAGE : "prefers"
```

---

## Language — Field Reference

| Field | Type | Description |
|---|---|---|
| `name` | Data | Auto: `LANG-.##` |
| `language_name` | Data | e.g. "English", "Hindi", "Marathi" |
| `language_code` | Data | e.g. "en", "hi", "mr" |
| `is_active` | Check | Inactive languages hidden from template selection |

**Seed data:** English (en), Hindi (hi), Marathi (mr)

---

## WhatsApp Message Template — Field Reference

| Field | Type | Description |
|---|---|---|
| `name` | Data | Auto: `WTPL-.##` |
| `template_name` | Data | Human-readable identifier |
| `message_type` | Select | One of 6 message types (see below) |
| `language` | Link → Language | Which language this template is in |
| `template_body` | Long Text | Message body with `{{placeholder}}` variables |
| `is_active` | Check | Inactive templates not used |

**Message Types:**
| Value | Trigger |
|---|---|
| `Order Confirmation` | Order submit |
| `Pickup Reminder` | Job Card → Ready |
| `Payment Thanks` | Payment Unpaid→Paid |
| `Win-Back` | Daily scheduler |
| `Scratch Card` | Job Card → Ready (5th order) |
| `VIP Thank You` | Manual from leaderboard |

**Available Placeholders:**
| Placeholder | Source |
|---|---|
| `{{customer_name}}` | `Laundry Customer.full_name` |
| `{{eta}}` | `Laundry Order.eta` (formatted) |
| `{{total_amount}}` | `Laundry Order.net_amount` |
| `{{upi_link}}` | Generated from `Spinly Settings.upi_id` |
| `{{lot_number}}` | `Laundry Order.lot_number` |
| `{{points_balance}}` | `Loyalty Account.total_points` |
| `{{discount_applied}}` | `Laundry Order.discount_amount` |
| `{{streak_progress}}` | `Laundry Order.streak_progress_text` |

**Total templates:** 6 types × 3 languages = **18 templates**

---

## WhatsApp Message Log — Field Reference

| Field | Type | Description |
|---|---|---|
| `name` | Data | Auto: `WLOG-.YYYY.-.#####` |
| `recipient_phone` | Data | Customer phone number |
| `customer` | Link → Laundry Customer | Sender identity |
| `message_type` | Data | Which of the 6 types was sent |
| `template_used` | Link → WhatsApp Message Template | Which template was rendered |
| `order` | Link → Laundry Order | Optional — blank for Win-Back and VIP messages |
| `status` | Select | `Queued` (Phase 1 stub) / `Sent` / `Failed` |
| `sent_at` | Datetime | Timestamp of send attempt |
| `error_message` | Small Text | Provider error if status = Failed |

> In Phase 1, all log entries are `Queued`. The log is the proof-of-delivery record for Phase 2 auditing.

---

## Related
- [[04 - Notifications/_Index]]
- [[04 - Notifications/Business Logic]]
- [[05 - Configuration & Masters/Data Model]]
- [[📊 DocType Map]]
