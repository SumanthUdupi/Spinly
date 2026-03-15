---
tags: [index, moc, spinly]
module: Root
type: index
status: spec-approved
linked_doctypes: []
---

# 🏠 Spinly — Master Index

Spinly is a hyper-simplified, mobile-first laundry management system built as a custom Frappe app. It provides a **low-click, icon-driven interface** for blue-collar staff and a full-featured manager dashboard — automating ETA calculation, machine allocation, consumable inventory deduction, and customer loyalty without touching ERPNext's accounting module.

**Framework:** Frappe v17 · **Database:** MariaDB · **Namespace:** `spinly` · **Site:** `dev.localhost`

---

## Hard Constraints

| Constraint | Rule |
|---|---|
| No Accounting | Zero Journal Entries, GL Entries, or Payment Entries ever created. Payment = binary `Paid/Unpaid` toggle only. |
| Low-Click | Returning customer order: ≤ 5 taps. New customer registration: ≤ 7 taps (one-time exception). Job Card advance: 1 tap. |
| No Coding to Maintain | All category data managed via Frappe Desk CRUD. No terminal access needed post-launch. |
| Offline (Phase 2) | Phase 1 assumes stable WiFi. Offline queuing deferred. |

---

## System Map

```mindmap
root((Spinly))
  Order Flow
    Data Model
    ETA & Machine Allocation
    Job Card Lifecycle
    POS UI
    Testing
  Loyalty & Gamification
    Data Model
    Points Engine
    Promo Campaigns
    UI
    Testing
  Inventory
    Data Model
    Deduction Logic
    Restock
    Testing
  Notifications
    WhatsApp Templates
    6 Trigger Points
    Multilingual
    Testing
  Configuration & Masters
    10 Master DocTypes
    Spinly Settings
    Manager Dashboard
    Testing
  System
    Roles & Permissions
    Print Formats
    Background Jobs
    Mock Data & Fixtures
```

---

## Vault Navigation

### Root Reference
| File | Purpose |
|---|---|
| [[📊 DocType Map]] | All 21 DocTypes + full ER diagram |
| [[🔗 Hook Map]] | Complete hooks.py visualised as diagrams |
| [[🏗️ Architecture]] | System topology, file structure, Approach D |

### Feature Modules
| Folder | Description |
|---|---|
| [[01 - Order Flow/_Index]] | Customer → Order → Job Card → Delivery |
| [[02 - Loyalty & Gamification/_Index]] | Points, Tiers, Streaks, Promos, Scratch Cards |
| [[03 - Inventory/_Index]] | Consumable deduction + restock |
| [[04 - Notifications/_Index]] | WhatsApp stubs + 6 trigger flows |
| [[05 - Configuration & Masters/_Index]] | 10 master DocTypes + Spinly Settings |
| [[06 - System/_Index]] | Roles, Print Formats, Scheduler, Fixtures |

### All Documents
| # | Document | Module |
|---|---|---|
| 1 | [[📊 DocType Map]] | Root |
| 2 | [[🔗 Hook Map]] | Root |
| 3 | [[🏗️ Architecture]] | Root |
| 4 | [[01 - Order Flow/_Index]] | Order Flow |
| 5 | [[01 - Order Flow/Data Model]] | Order Flow |
| 6 | [[01 - Order Flow/Business Logic — ETA & Machine Allocation]] | Order Flow |
| 7 | [[01 - Order Flow/Business Logic — Job Card Lifecycle]] | Order Flow |
| 8 | [[01 - Order Flow/UI]] | Order Flow |
| 9 | [[01 - Order Flow/Testing]] | Order Flow |
| 10 | [[02 - Loyalty & Gamification/_Index]] | Loyalty |
| 11 | [[02 - Loyalty & Gamification/Data Model]] | Loyalty |
| 12 | [[02 - Loyalty & Gamification/Business Logic]] | Loyalty |
| 13 | [[02 - Loyalty & Gamification/UI]] | Loyalty |
| 14 | [[02 - Loyalty & Gamification/Testing]] | Loyalty |
| 15 | [[03 - Inventory/_Index]] | Inventory |
| 16 | [[03 - Inventory/Data Model]] | Inventory |
| 17 | [[03 - Inventory/Business Logic]] | Inventory |
| 18 | [[03 - Inventory/UI]] | Inventory |
| 19 | [[03 - Inventory/Testing]] | Inventory |
| 20 | [[04 - Notifications/_Index]] | Notifications |
| 21 | [[04 - Notifications/Data Model]] | Notifications |
| 22 | [[04 - Notifications/Business Logic]] | Notifications |
| 23 | [[04 - Notifications/UI]] | Notifications |
| 24 | [[04 - Notifications/Testing]] | Notifications |
| 25 | [[05 - Configuration & Masters/_Index]] | Config |
| 26 | [[05 - Configuration & Masters/Data Model]] | Config |
| 27 | [[05 - Configuration & Masters/Business Logic]] | Config |
| 28 | [[05 - Configuration & Masters/UI]] | Config |
| 29 | [[05 - Configuration & Masters/Testing]] | Config |
| 30 | [[06 - System/_Index]] | System |
| 31 | [[06 - System/Roles & Permissions]] | System |
| 32 | [[06 - System/Print Formats]] | System |
| 33 | [[06 - System/Background Jobs]] | System |
| 34 | [[06 - System/Mock Data & Fixtures]] | System |

---

## Sprint Overview

| Sprint | Days | Scope |
|---|---|---|
| Sprint 1 — Foundation | 1–4 | App scaffold, all 21 DocTypes, fixtures, roles, settings |
| Sprint 2 — Core Order Flow | 5–9 | ETA engine, Job Card, consumable deduction, POS page, print formats |
| Sprint 3 — WhatsApp & Payments | 10–12 | WhatsApp stub, 6 triggers, payment toggle, restock log |
| Sprint 4 — Loyalty & Gamification | 13–17 | Points, tiers, streaks, scratch cards, promo engine |
| Sprint 5 — Dashboard & Polish | 18–21 | Manager workspace, KPIs, leaderboard, mock data, full test run |
| Phase 2 (Future) | — | Real WhatsApp provider, offline queuing, Driver Module |

---

## Quick Reference

### Roles
| Role | Surface |
|---|---|
| Laundry Staff | `/spinly-pos` (redirected on login) |
| Laundry Manager | Frappe Desk — full workspace |
| System Manager | Full access including scheduler logs |

### Color System
| Color | Meaning |
|---|---|
| 🟢 Green | Done / Go — Completed steps, Paid, Idle machines |
| 🟡 Yellow | In Progress — Current step, Running machines |
| 🔴 Red | Action Required — Alerts, Out of Order, Unpaid overdue |
| 🔵 Blue | Info — ETA, tier badges |

### DocType Count
| Category | Count |
|---|---|
| Category Masters | 6 |
| Configuration Masters | 4 |
| CRM Master | 1 |
| Transactional | 4 |
| Gamification | 2 |
| Logs / Audit | 2 |
| Child Tables | 2 |
| **Total** | **21** |
