---
tags: [testing, inventory]
module: Inventory
type: testing
status: spec-approved
linked_doctypes: [Laundry Consumable, Inventory Restock Log, Laundry Job Card]
---

# Testing — Inventory

---

## Deduction Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| IN-01 | Basic deduction | Job Card submitted. Order = 5 kg. Detergent Pro: consumption_per_kg = 30 ml. | Detergent Pro current_stock decremented by 150 ml (5 × 30). |
| IN-02 | All consumables deducted | 6 active consumables. Job Card submitted. | All 6 consumables decremented proportional to order weight. |
| IN-03 | Deduction only on submit | Job Card saved (not submitted). | No deduction. Deduction fires on_submit only. |
| IN-04 | Multiple Job Cards | 3 Job Cards submitted with 4 kg, 6 kg, 2 kg orders. | Each deducts independently — cumulative correct total. |
| IN-05 | Stock not below threshold | Detergent Pro: 4500 ml, threshold 500 ml. 5 kg order → deduction 150 ml. new_stock = 4350 ml. | No alert created. |

---

## Low-Stock Alert Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| IN-06 | Alert on threshold breach | Fabric Softener: 420 ml, threshold 400 ml. 3 kg order → deduction 30 ml. new_stock = 390 ml. | Alert notification created for System Manager role. |
| IN-07 | Alert shows correct item | Multiple consumables below threshold. | One alert per consumable breach — correct item_name in each. |
| IN-08 | Seed state alerts visible | Load fixture data. Open Dashboard. | 3 low-stock alerts visible (Fabric Softener, Whitener, Dry Clean Solvent). |

---

## Restock Tests

| # | Test | Setup | Expected Result |
|---|---|---|---|
| IN-09 | Restock increments stock | Fabric Softener: 380 ml. Create Restock Log: quantity_added = 1000. | current_stock = 1380 ml after save. |
| IN-10 | apply_restock fires automatically | Restock Log inserted. | `inventory.apply_restock()` fires via after_insert hook — no manual step. |
| IN-11 | Multiple restocks accumulate | Two Restock Logs: +500, +300. Initial stock 200. | Final current_stock = 1000. |
| IN-12 | Restock does not affect other consumables | Restock Log for Detergent Pro only. | Only Detergent Pro stock changes — all others unchanged. |

---

## Edge Case Tests

| # | Test | Expected Result |
|---|---|---|
| IN-13 | Zero weight order | Order total_weight_kg = 0. Job Card submitted. | Deduction = 0. current_stock unchanged. No alert. |
| IN-14 | Inactive consumable | Consumable set is_active = 0. Job Card submitted. | Inactive consumable NOT deducted. |

---

## Related
- [[03 - Inventory/_Index]]
- [[03 - Inventory/Business Logic]]
- [[01 - Order Flow/Testing]]
- [[06 - System/Mock Data & Fixtures]]
