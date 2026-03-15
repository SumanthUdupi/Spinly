---
tags: [testing, loyalty, gamification, promos]
module: Loyalty & Gamification
type: testing
status: spec-approved
linked_doctypes: [Loyalty Account, Loyalty Transaction, Promo Campaign, Scratch Card]
---

# Testing — Loyalty & Gamification

---

## Points Engine Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| LY-01 | Points earned on submit | Order: 5 kg, Wash & Fold (₹40/kg). Settings: 10 pts/kg, 0.5 pts/₹. | `max(5×10=50, 200×0.5=100) = 100 pts` earned. Loyalty Transaction (Earn) created. |
| LY-02 | net_amount used for currency points | Order: ₹200 total, ₹20 discount → net ₹180. | Currency pts = `180 × 0.5 = 90`. Weight pts compared to 90. max() applied. |
| LY-03 | Points balance updated | Before: 200 total_pts, 400 lifetime_pts. Earn 100 pts. | total_points = 300, lifetime_points = 500. |
| LY-04 | order_count incremented | Customer's 4th order submitted. | order_count = 4 after submit. |
| LY-05 | Points expiry set | Earn transaction created. `points_expiry_days = 90`. | `expiry_date = today + 90 days` on Loyalty Transaction. |

---

## Tier Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| TI-01 | Bronze → Silver upgrade | Customer at 490 lifetime pts earns 20 pts. | lifetime_pts = 510 → tier upgrades to Silver. |
| TI-02 | Silver → Gold upgrade | Customer at 1980 lifetime pts earns 50 pts. | lifetime_pts = 2030 → tier upgrades to Gold. |
| TI-03 | Tier stable when spending pts | Gold customer redeems 500 pts. | total_points decrements, lifetime_points unchanged → tier stays Gold. |
| TI-04 | Monthly recalculate_all_tiers | Customer manually edited to incorrect tier. | Monthly job corrects tier from lifetime_points. |

---

## Streak Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| SK-01 | Streak increments | Previous order 5 days ago, new order today. | current_streak_weeks = previous + 1. |
| SK-02 | Streak resets on gap | Previous order 10 days ago, new order today. | current_streak_weeks = 1 (reset). |
| SK-03 | Streak progress text (in progress) | streak = 3, streak_weeks_required = 4. | streak_progress_text = "3/4 weeks — 1 more for double points!" |
| SK-04 | Streak completion — double points | streak reaches 4 (streak_weeks_required = 4). | Bonus Loyalty Transaction created (points = same as this order's earn). total_points += bonus. current_streak_weeks = 0. |
| SK-05 | Streak progress text (complete) | Streak completed. | streak_progress_text = "Streak complete! Double points awarded!" |
| SK-06 | First order — no streak | Customer's first ever order. | previous_order_date = None → days_since_last = 999 → streak = 1 (start). |

---

## Promo Campaign Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| PR-01 | Flash Sale applied | Active Flash Sale: 20% off Dry Clean. Order = Dry Clean. | discount_amount = 20% of total_amount. applied_promo set. |
| PR-02 | Flash Sale — wrong service | Active Flash Sale: 20% off Dry Clean. Order = Wash & Fold. | No discount. applied_promo blank. |
| PR-03 | Weight Milestone applied | Campaign: free ironing on orders > 10 kg. Order = 12 kg. | Discount applied. applied_promo set. |
| PR-04 | Weight Milestone — below threshold | Campaign: > 10 kg. Order = 8 kg. | No discount applied. |
| PR-05 | Birthday promo | Customer DOB month = current month. Birthday campaign active. | Discount applied. |
| PR-06 | Birthday promo — wrong month | Customer DOB month ≠ current month. | No discount. |
| PR-07 | Priority stack | Flash Sale (priority 10) + Weight Milestone (priority 5) both eligible. | Only Flash Sale applied (highest priority). discount_amount from Flash Sale only. |
| PR-08 | Win-Back handled by scheduler | Customer inactive 35 days. New order placed. | Win-Back NOT applied at order level. Scheduler handles WhatsApp separately. |
| PR-09 | Inactive campaign ignored | Campaign is_active = 0. | Not included in eligible list. |
| PR-10 | Expired campaign ignored | active_to < today. | Not included in eligible list. |

---

## Scratch Card Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| SC-01 | 5th order triggers scratch card | Customer's 5th order (order_count = 5). Job Card → Ready. | Scratch Card DocType created (status=Pending). WhatsApp Message Log entry queued. |
| SC-02 | Non-5th order no scratch card | Customer's 3rd order. Job Card → Ready. | No Scratch Card created. |
| SC-03 | 10th order triggers scratch card | Customer's 10th order (order_count = 10, frequency = 5). | Scratch Card created (10 % 5 == 0). |
| SC-04 | scratch_card_frequency config | Change scratch_card_frequency to 3. Customer's 3rd order. | Scratch Card created (3 % 3 == 0). |
| SC-05 | issued_via_whatsapp flag set | Scratch card issued. | `issued_via_whatsapp = 1` after WhatsApp message queued. |

---

## Referral Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| RF-01 | First order referral bonus | New customer A, referred_by = Customer B. A submits first order. Referral campaign active with 50 bonus pts. | Customer A gets +50 pts (Referral txn). Customer B gets +50 pts (Referral txn). |
| RF-02 | Referral only on first order | Customer A submits 2nd order. referred_by = Customer B. | No referral bonus. Only fires when order_count == 1. |
| RF-03 | No active Referral campaign | No Promo Campaign of type Referral is active. Customer A's first order. | No referral bonus awarded (no campaign to reference). |

---

## Points Expiry Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| EX-01 | Daily expiry job | Earn transaction with expiry_date = yesterday. | Expire transaction created. total_points decremented. |
| EX-02 | Future expiry not expired | Earn transaction with expiry_date = tomorrow. | Not expired. total_points unchanged. |
| EX-03 | total_points floor | Customer has 30 pts, 50 pts expire. | total_points = max(0, 30 - 50) = 0. Never negative. |

---

## Redeem Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| RD-01 | Redeem at checkout | Customer applies 100 pts (= ₹10 off, redemption_rate = 100pts/₹10). | loyalty_points_redeemed = 100. discount_amount += 10. Redeem Loyalty Transaction created. total_points -= 100. |
| RD-02 | Redeem does not affect lifetime_pts | Customer redeems 200 pts. lifetime_points = 1500. | lifetime_points still = 1500. Tier unchanged. |

---

## Related
- [[02 - Loyalty & Gamification/_Index]]
- [[02 - Loyalty & Gamification/Business Logic]]
- [[01 - Order Flow/Testing]]
- [[04 - Notifications/Testing]]
- [[06 - System/Mock Data & Fixtures]]
