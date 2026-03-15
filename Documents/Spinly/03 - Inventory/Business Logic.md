---
tags: [business-logic, inventory, deduction, restock]
module: Inventory
type: business-logic
status: spec-approved
linked_doctypes: [Laundry Consumable, Inventory Restock Log, Laundry Job Card]
---

# Business Logic — Inventory

**File:** `spinly/logic/inventory.py`

---

## deduct_consumables() — Full Flow

**Triggered:** `Laundry Job Card → on_submit`

```mermaid
flowchart TD
    START([Laundry Job Card on_submit])
    GET_ORDER["Get linked Laundry Order\nFetch order.total_weight_kg"]
    FETCH["Fetch all active Laundry Consumables\n(no filter on category — all consumables deducted)"]
    LOOP["For each consumable:"]
    CALC["deduction = total_weight_kg × consumable.consumption_per_kg"]
    UPDATE["new_stock = consumable.current_stock - deduction\nfrappe.db.set_value('Laundry Consumable', name, 'current_stock', new_stock)"]
    CHECK{"new_stock <\nreorder_threshold?"}
    ALERT["frappe.sendmail() OR frappe.get_doc notification\nRole: System Manager\nMessage: 'Low stock: {item_name} at {new_stock} {unit}'"]
    NEXT["Next consumable"]
    DONE([Done])

    START --> GET_ORDER --> FETCH --> LOOP
    LOOP --> CALC --> UPDATE --> CHECK
    CHECK -->|Yes| ALERT --> NEXT
    CHECK -->|No| NEXT
    NEXT -->|More| LOOP
    NEXT -->|Done| DONE
```

---

## Deduction Formula

```
deduction = order.total_weight_kg × consumable.consumption_per_kg
new_stock = consumable.current_stock - deduction
```

**Example:**
- Order weight: 5 kg
- Detergent Pro consumption_per_kg: 30 ml/kg
- Deduction: 5 × 30 = **150 ml**
- If current_stock was 4500 ml → new_stock = **4350 ml**

> Deduction is **weight-based**, not garment-type-based. Every kg of laundry deducts the same amount regardless of garment type (shirts, sarees, bedding — all treated equally).

---

## Why frappe.db.set_value (not doc.save)

`frappe.db.set_value` writes directly to the database without triggering hooks. This is intentional:
- **Performance:** Avoids re-triggering on_update hooks for each consumable during batch processing
- **Safety:** Prevents recursive hook chains
- **Accuracy:** `current_stock` is a simple numeric field — no business logic on update needed

---

## Low-Stock Alert

When `new_stock < reorder_threshold` after deduction:
- Frappe notification created for **System Manager** role
- Notification includes: item_name, new_stock, unit, reorder_threshold, reorder_quantity (suggested)
- Alert appears on Manager Dashboard as a red highlight row

---

## apply_restock() — Full Flow

**Triggered:** `Inventory Restock Log → after_insert`

```mermaid
flowchart TD
    START([Inventory Restock Log after_insert])
    GET["Get linked Laundry Consumable\ndoc = frappe.get_doc('Laundry Consumable', log.consumable)"]
    ADD["doc.current_stock += log.quantity_added"]
    SAVE["doc.save()"]
    DONE([Done — stock incremented])

    START --> GET --> ADD --> SAVE --> DONE
```

```python
def apply_restock(doc, method):
    consumable = frappe.get_doc("Laundry Consumable", doc.consumable)
    consumable.current_stock += doc.quantity_added
    consumable.save()
```

> The manager never needs to manually update `current_stock`. Creating a Restock Log entry is the only required action.

---

## Anti-Patterns

- ❌ Never deduct stock on Order submit — only on **Job Card submit** (when work actually starts)
- ❌ Never manually edit `current_stock` — always use Inventory Restock Log for additions
- ❌ Never allow `current_stock` to go negative — add validation if needed
- ❌ Never deduct based on garment type — deduction is always weight × consumption_per_kg

---

## Related
- [[03 - Inventory/_Index]]
- [[03 - Inventory/Data Model]]
- [[01 - Order Flow/Business Logic — Job Card Lifecycle]]
- [[🔗 Hook Map]]
