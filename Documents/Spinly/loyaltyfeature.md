Loyalty & Gamification Feature Set for Spinly                                                                                                               
                                                                                                                                                                
    As a Laundry Business Owner                                                                                                                                 
                                                                                                                                                                
    What actually drives repeat visits:                                                                                                                         
    - Customers forget you exist between visits — you need a reason to come back
    - Discounts eat margin; gamification creates perceived value without cash cost
    - The most powerful loyalty tool in laundry is predictability (same-day slots, reserved machines)

    ---
    Core Loyalty Features

    Points Engine (DocType: Loyalty Account)
    - Earn X points per kg or per order value
    - Points have an expiry (e.g., 90 days) to drive urgency
    - Redemption: 100 points = ₹10 off
    - Staff sees a single prompt: "Apply 50 pts for ₹5 off?" — one tap

    Tier System (Bronze / Silver / Gold)
    - Bronze: 0–500 pts lifetime → standard pricing
    - Silver: 500–2000 pts → priority queue (ETA bumped up), 5% discount
    - Gold: 2000+ pts → free pickup bag, 10% discount, dedicated WhatsApp line
    - Tier badge shown on Job Card so staff treat Gold customers visibly better

    ---
    Discount Campaigns (DocType: Promo Campaign)**

    ┌──────────────────┬──────────────────────────┬──────────────────────────────────────────────────┐
    │  Campaign Type   │         Trigger          │                     Example                      │
    ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
    │ Flash Sale       │ Date/time window         │ "20% off Dry Clean, Tue only"                    │
    ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
    │ Weight Milestone │ Order > N kg             │ "Orders above 10 kg get free ironing"            │
    ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
    │ Win-Back         │ No order in 30 days      │ Auto-WhatsApp: "We miss you — 15% off this week" │
    ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
    │ Birthday Reward  │ DOB on customer record   │ Free wash on birthday month                      │
    ├──────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
    │ Referral         │ New customer cites phone │ Both get 50 bonus points                         │
    └──────────────────┴──────────────────────────┴──────────────────────────────────────────────────┘

    Campaigns have a priority stack — only the highest-priority active promo applies per order (no stacking), keeping margin predictable.

    ---
    Gamification Layer

    Scratch Card (Post-pickup WhatsApp)
    - After every 5th order: customer gets a WhatsApp link to a digital scratch card
    - Prizes: 10% off, free bag, bonus points, or "Better luck next time"
    - Costs nothing to run, creates genuine excitement

    Streak Bonus
    - "Wash 4 weeks in a row → earn Double Points Week"
    - Shown on the receipt: "3/4 weeks — one more to unlock double points!"

    Leaderboard (Owner Dashboard only)
    - Top 10 customers by monthly spend
    - Owner can manually send a "VIP Thank You" WhatsApp to top 3

    ---
    As a Developer — How It Fits Spinly's Architecture

    DocTypes to add:
    - Loyalty Account (linked to Laundry Customer, tracks points + tier)
    - Loyalty Transaction (ledger: earn/redeem events)
    - Promo Campaign (date range, discount type, conditions)
    - Scratch Card (linked to Order, status: pending/scratched)

    Hooks:
    - Laundry Order → on_submit → loyalty.earn_points()
    - Laundry Order → before_save → promo.apply_best_discount()
    - Laundry Job Card → on status→"Ready" → scratch_card.issue_if_eligible()

    WhatsApp triggers:
    - Win-back: daily background job checks last_order_date
    - Streak check: weekly job evaluates consecutive weeks
    - Scratch card: send link when Job Card hits "Ready" on qualifying orders

    ---
    Anti-Patterns to Avoid

    - Don't build a separate customer app — WhatsApp is the loyalty channel (per BRD)
    - Don't make tiers complex — staff must never need to calculate anything
    - Don't let discounts touch accounting — apply as a simple discount_amount field on the order, not a credit note or journal entry

    ---
    This fits cleanly into Phase 1.5 — after core order flow is stable, before Phase 2 (Driver Module). It can ship as a toggle in Spinly Settings:
    enable_loyalty_program: Yes/No.