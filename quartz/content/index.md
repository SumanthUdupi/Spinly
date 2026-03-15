---
title: Spinly Documentation
---

# 🏠 Spinly — Laundry Management System

Spinly is a hyper-simplified, mobile-first laundry management system built on Frappe Framework. This documentation covers the complete system design — ready for review before development begins.

> **Status:** Spec approved · **Framework:** Frappe v17 · **Namespace:** `spinly`

---

## Navigate the Docs

| Section | Description |
|---|---|
| [[📊 DocType Map]] | All 21 DocTypes with full ER diagram |
| [[🔗 Hook Map]] | Complete hooks.py visualised as sequence diagrams |
| [[🏗️ Architecture]] | System topology, file structure, Approach D |
| [[01 - Order Flow/_Index\|01 · Order Flow]] | Customer → Order → Job Card → Delivery |
| [[02 - Loyalty & Gamification/_Index\|02 · Loyalty & Gamification]] | Points, Tiers, Streaks, Promos, Scratch Cards |
| [[03 - Inventory/_Index\|03 · Inventory]] | Consumable deduction + restock |
| [[04 - Notifications/_Index\|04 · Notifications]] | WhatsApp stubs + 6 trigger flows |
| [[05 - Configuration & Masters/_Index\|05 · Configuration & Masters]] | 10 master DocTypes + Spinly Settings |
| [[06 - System/_Index\|06 · System]] | Roles, Print Formats, Scheduler, Fixtures |

---

## Hard Constraints

| Constraint | Rule |
|---|---|
| **No Accounting** | Zero Journal Entries, GL Entries, or Payment Entries. Ever. |
| **Low-Click** | Returning customer order ≤ 5 taps. Job Card advance = 1 tap. |
| **No Coding to Maintain** | All category data via Frappe Desk CRUD. |
| **Offline (Phase 2)** | Phase 1 assumes WiFi. Offline queuing deferred. |
