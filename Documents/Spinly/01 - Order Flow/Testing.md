---
tags: [testing, order-flow, eta, low-click]
module: Order Flow
type: testing
status: spec-approved
linked_doctypes: [Laundry Order, Laundry Job Card, Laundry Machine]
---

# Testing — Order Flow

---

## ETA Engine Tests

| # | Scenario | Setup | Expected Result |
|---|---|---|---|
| ETA-01 | Machine at full capacity | MAC-01 (10 kg cap) already has 10 kg load. Order = 3 kg. | System skips MAC-01, allocates to next eligible machine |
| ETA-02 | All machines full | All eligible machines at capacity | ETA = next available slot (earliest countdown_timer_end across all machines) |
| ETA-03 | Maintenance Required excluded | MAC-04 status = Maintenance Required | MAC-04 never appears in allocation pool |
| ETA-04 | Out of Order excluded | MAC-05 status = Out of Order | MAC-05 never appears in allocation pool |
| ETA-05 | Silver tier priority | Silver customer, MAC-02 (4 kg load) and MAC-01 (8 kg load) eligible | Assigned to MAC-02 (least loaded) → lower T_queue → earlier ETA |
| ETA-06 | Gold tier priority | Gold customer, multiple eligible machines | Assigned to least-loaded machine → earliest possible ETA |
| ETA-07 | Shift overflow | Shift ends 20:00. Calculated ETA = 20:30 | ETA rolls to next day: shift_start + 30 min overflow |
| ETA-08 | Order 30 min before shift end | Shift ends 20:00, order at 19:35, service = 60 min | ETA overflows: next day shift_start + 35 min |
| ETA-09 | Two simultaneous orders | Two orders submitted in quick succession, same machine eligible | No double-allocation: second order sees updated load after first |
| ETA-10 | Bronze vs Silver same time | Bronze and Silver order at same time, one machine available | Silver gets the machine (priority allocation) — Bronze waits for next available |

---

## Low-Click Tests

| # | Staff Action | Max Taps | Verification Method |
|---|---|---|---|
| LC-01 | New order for returning customer | ≤ 5 from POS home | Manual tap count on live POS |
| LC-02 | New order for new customer | ≤ 7 from POS home | Manual tap count (name + phone = 2 fields, exception allowed) |
| LC-03 | Advance Job Card one step | 1 tap | Single [NEXT STEP] button render check |
| LC-04 | Mark order as Paid | 1 tap | [MARK AS PAID] button at Ready/Delivered stage |
| LC-05 | Apply loyalty discount at checkout | 1 tap | [YES] on "Apply X pts?" prompt at Screen 3 |
| LC-06 | Mark machine Out of Order | 1 tap from machine list | Machine status button in Manager Desk |

---

## No-Accounting Constraint Tests

| # | Test | Action | Pass Condition |
|---|---|---|---|
| NA-01 | Submit orders | Submit 55 orders via POS | Zero Journal Entries, GL Entries, Payment Entries in ERPNext |
| NA-02 | Mark orders Paid | Toggle payment_status on 30 orders | `payment_status = Paid` only — no ledger movement |
| NA-03 | Apply loyalty discount | Redeem points on 5 orders | Only `discount_amount` field updated on order. No credit note. |
| NA-04 | Apply promo discount | Flash Sale active, submit Dry Clean order | Only `discount_amount` field updated. No credit note. |
| NA-05 | ERPNext Accounts audit | Check ERPNext → Accounting module | Zero new entries after full test run |

---

## Job Card Workflow Tests

| # | Test | Expected Result |
|---|---|---|
| JC-01 | Order submitted | Job Card created at `Sorting` state with correct lot_number, machine, tier_badge |
| JC-02 | Job Card → Running | machine.countdown_timer_end updated on Laundry Machine |
| JC-03 | Job Card → Ready | WhatsApp Pickup Reminder queued in Message Log |
| JC-04 | Job Card → Ready (5th order) | Scratch Card DocType created + WhatsApp Scratch Card queued |
| JC-05 | Job Card submitted | Consumable stock decremented by (order_weight × consumption_per_kg) |
| JC-06 | Tier badge accuracy | Gold customer → customer_tier_badge = Gold on Job Card |

---

## Pass/Fail Criteria

| Test Suite | Pass Condition |
|---|---|
| ETA Engine | All 10 scenarios produce correct machine + ETA. No double-allocation. |
| Low-Click | All 6 actions within tap budget. Verified on physical device (tablet + phone). |
| No-Accounting | Zero accounting entries in ERPNext after complete test run. |
| Job Card | All workflow transitions trigger correct hooks. Tier badge always accurate. |

---

## Related
- [[01 - Order Flow/_Index]]
- [[01 - Order Flow/Business Logic — ETA & Machine Allocation]]
- [[01 - Order Flow/Business Logic — Job Card Lifecycle]]
- [[02 - Loyalty & Gamification/Testing]]
- [[03 - Inventory/Testing]]
- [[04 - Notifications/Testing]]
- [[06 - System/Mock Data & Fixtures]]
