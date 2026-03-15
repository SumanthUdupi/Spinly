---
tags: [testing, configuration, masters]
module: Configuration & Masters
type: testing
status: spec-approved
linked_doctypes: [Garment Type, Alert Tag, Payment Method, Laundry Machine, Spinly Settings]
---

# Testing — Configuration & Masters

---

## Configurable Categories Tests

| # | Test | Action | Expected Result |
|---|---|---|---|
| CM-01 | Add new Garment Type | Create Garment Type: "Curtain 🪟", sort_order=7, is_active=1. | Curtain appears in POS Screen 2 icon grid at position 7. No code change. |
| CM-02 | Deactivate Garment Type | Set Shirt is_active=0. | Shirt no longer appears in POS icon grid. Existing orders unaffected. |
| CM-03 | Add new Alert Tag | Create Alert Tag: "Hand Wash Only 🤲", color=#3B82F6. | New tag button appears in POS Screen 2. Correct blue color. |
| CM-04 | Deactivate Alert Tag | Set "Heavy Soil" is_active=0. | Heavy Soil button disappears from POS. Existing orders with this tag unaffected. |
| CM-05 | Add new Payment Method | Create Payment Method: "Bank Transfer", show_upi_qr=No. | Payment method appears at POS checkout screen. |
| CM-06 | Add new Language + templates | Create Language "Tamil (ta)". Create 6 WhatsApp templates in Tamil. | Customer with language_preference=Tamil receives Tamil templates. No code change. |
| CM-07 | Add new Promo Campaign | Create Flash Sale: 15% off Wash & Iron, valid today, priority=8. | Campaign auto-applies to Wash & Iron orders placed today. |
| CM-08 | Deactivate Promo Campaign | Set Flash Sale is_active=0. | No discount applied on new orders. Existing discounted orders unaffected. |

---

## Machine Status Tests

| # | Test | Action | Expected Result |
|---|---|---|---|
| MC-01 | Mark machine Out of Order | Set MAC-01 status = Out of Order. Place new order. | MAC-01 not in allocation pool. ETA engine skips it. |
| MC-02 | Restore machine to Idle | Set MAC-04 status = Idle (after maintenance). Place new order. | MAC-04 re-enters allocation pool. |
| MC-03 | Running machine has capacity | MAC-02 (8 kg cap) has 4 kg load. New 3 kg order. | MAC-02 eligible (4+3=7 ≤ 8). Allocated. |
| MC-04 | Running machine at capacity | MAC-02 (8 kg cap) has 8 kg load. New 3 kg order. | MAC-02 skipped (8+3=11 > 8). Next machine tried. |

---

## Spinly Settings Toggle Tests

| # | Test | Action | Expected Result |
|---|---|---|---|
| SS-01 | Disable loyalty | Set enable_loyalty_program = No. Submit order. | No points earned. No discount applied. No loyalty prompt on POS. |
| SS-02 | Change points rate | Set points_per_kg = 20 (was 10). Submit 5 kg order. | Earn 100 pts (5×20) or currency-based, whichever higher. |
| SS-03 | Change tier threshold | Set tier_silver_pts = 300 (was 500). | Next recalculate or earn event: customers with 300+ lifetime pts upgrade to Silver. |
| SS-04 | Change scratch card frequency | Set scratch_card_frequency = 3 (was 5). Customer's 3rd order → Job Card → Ready. | Scratch Card created (3 % 3 == 0). |
| SS-05 | Change shift end time | Set shift_start = 10:00, shift_duration_hrs = 8 (shift ends 18:00). Order at 17:50 with 60 min service. | ETA overflows to next day: 10:00 + 50 min = 10:50 next day. |

---

## Related
- [[05 - Configuration & Masters/_Index]]
- [[05 - Configuration & Masters/Business Logic]]
- [[01 - Order Flow/Testing]]
- [[06 - System/Mock Data & Fixtures]]
