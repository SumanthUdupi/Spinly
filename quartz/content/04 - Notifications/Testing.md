---
tags: [testing, notifications, whatsapp]
module: Notifications
type: testing
status: spec-approved
linked_doctypes: [WhatsApp Message Log, WhatsApp Message Template, Language]
---

# Testing — Notifications

All Phase 1 tests verify `WhatsApp Message Log` entries. No actual WhatsApp messages are sent.

---

## Stub Tests — All 6 Message Types

| # | Trigger | Action | Expected Log Entry |
|---|---|---|---|
| WA-01 | Order Confirmation | Submit a Laundry Order | `status=Queued`, `message_type=Order Confirmation`, `recipient_phone=customer.phone`, correct `lot_number` and `eta` in rendered message |
| WA-02 | Pickup Reminder | Advance Job Card to `Ready` | `status=Queued`, `message_type=Pickup Reminder`, `upi_link` populated from `Spinly Settings.upi_id` |
| WA-03 | Payment Thanks | Toggle `payment_status` from Unpaid → Paid on a submitted order | `status=Queued`, `message_type=Payment Thanks`, `customer_name` and `points_earned` in context |
| WA-04 | Payment Thanks guard | Save an already-Paid order again (no status change) | No new Message Log entry created (guard prevents duplicate) |
| WA-05 | Win-Back | Run daily scheduler. Customer with `last_order_date` = 36 days ago. | One `status=Queued` entry, `message_type=Win-Back`, for that customer |
| WA-06 | Win-Back threshold | Customer with `last_order_date` = 25 days ago (below win_back_days=30). | No Win-Back message. |
| WA-07 | Scratch Card | Customer's 5th order. Job Card → Ready. | `status=Queued`, `message_type=Scratch Card`, `scratch_card_link` populated |
| WA-08 | VIP Thank You | Manager taps [Send VIP] on leaderboard for top customer. | `status=Queued`, `message_type=VIP Thank You`, correct customer name |

---

## Multilingual Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| ML-01 | Customer gets Hindi template | Customer language_preference = Hindi (hi). Order submitted. | Message Log uses Hindi template for Order Confirmation. |
| ML-02 | Fallback to default language | Customer language_preference = Tamil (no Tamil template exists). | Uses `default_language` template (English). |
| ML-03 | Add new language | Create Marathi templates. Set customer language = Marathi. Submit order. | Message Log uses Marathi template — no code change required. |
| ML-04 | Inactive template not used | Deactivate Hindi Order Confirmation template. Hindi-speaking customer submits order. | Falls back to default_language template. |

---

## Message Log Audit Tests

| # | Test | Expected Result |
|---|---|---|
| WA-09 | Log entry has correct phone | Customer phone = `9876543210`. Order submitted. | `recipient_phone = 9876543210` in log entry. |
| WA-10 | Log references order | Order Confirmation sent. | `order` field in log = the submitted order name. |
| WA-11 | Log references template | Order Confirmation sent. | `template_used` field = the matching WhatsApp Message Template record. |
| WA-12 | Win-Back log has no order | Win-Back WhatsApp sent. | `order` field is blank (win-back is not order-specific). |

---

## Related
- [[04 - Notifications/_Index]]
- [[04 - Notifications/Business Logic]]
- [[01 - Order Flow/Testing]]
- [[06 - System/Mock Data & Fixtures]]
