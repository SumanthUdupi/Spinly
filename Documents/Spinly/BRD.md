# 📄 Business Requirements Document (BRD)

## Project Name: Spinly (Laundry Smart Management System)

**Document Version:** 1.0

**Target Audience:** Development Team, Project Stakeholders, UI/UX Designers

---

## 1. Executive Summary

**Spinly** is a highly intuitive, mobile-first centralized management system for modern laundry outlets. While drawing feature inspiration from platforms like QDC (Quick Dry Cleaning), Spinly’s core differentiator is its **hyper-simplified, low-click interface** designed specifically for blue-collar workers. It automates complex backend tasks—such as dynamic ETA calculations, machine allocation, and consumable tracking—while presenting the staff with a visual, icon-driven workflow.

## 2. User Roles & Access Levels

To keep the app simple, the interface will dynamically change based on who logs in.

| Role | Core Responsibilities | App Interface Needs |
| --- | --- | --- |
| **Staff (Blue-Collar)** | Order intake, tagging, sorting, washing, status updates, handing over orders. | Massive buttons, icon-driven, color-coded, zero typing (dropdowns/voice-to-text), 1-click status changes. |
| **Manager/Owner** | Billing overview, inventory management, customer relations, machine maintenance. | Detailed dashboards, analytics, inventory settings, shift management. |

---

## 3. Functional Requirements

### 3.1. Customer & Order Intake (Low-Friction Workflow)

* **Quick Customer Search:** Search by phone number. If new, add with just Name and Number.
* **Visual Order Creation:** Staff tap icons (e.g., 👕 Shirt, 👖 Pants, 🛏️ Bedding) and use `+` / `-` buttons for quantity. Or, simply input total weight (e.g., 5.5 kg).
* **Service Selection:** Wash & Fold, Wash & Iron, Dry Clean.
* **Alert Tags (1-Click):** Red button for "Color Bleed Risk", White button for "Whites Only", Feather icon for "Delicates".

### 3.2. Bucketing & Internal Tracking (Job Cards)

* **Lot/Bucket Generation:** Once an order is placed, the system generates a unique **Lot Number**.
* **Internal Job Card (Digital & Printable):**
* Displays Machine Number allocated.
* Large visual alerts (e.g., ⚠️ **WHITES**, ⚠️ **HEAVY SOIL**).
* Step-by-step checklist (Sorting $\rightarrow$ Washing $\rightarrow$ Drying $\rightarrow$ Ironing). Staff simply tap "Next Step" to update the state.


* **Customer Bill:** Clean invoice showing item count, total cost, and estimated pickup date/time.

### 3.3. WhatsApp Integration & Notifications

* **Automated Triggers:** * *Order Placed:* Sends digital receipt and ETA to the customer's WhatsApp.
* *Order Ready:* Sends pickup reminder + UPI payment link.
* *Payment Received:* Sends Thank You / Acknowledgment message.


* *Note:* Eliminates the need for a dedicated customer app by using WhatsApp as the primary communication channel.

### 3.4. Dynamic ETA Calculation

The system will calculate the Estimated Time of Arrival (ETA) for order completion automatically.

**Variables:**

* $W$: Weight of the current order (kg)
* $C_{m}$: Capacity of available machine $m$ (kg)
* $T_{s}$: Base processing time for the requested service (minutes)
* $Q_{time}$: Queue time of pending orders already assigned to machine $m$
* $S_{end}$: Shift end time (based on a 10-hour shift limit)

**Logic for ETA:**

1. **Machine Allocation:** The system finds the first available machine $m$ where current pending load + $W \le C_{m}$.
2. **Processing Time:**

$$T_{total} = Q_{time} + T_{s}$$


3. **Shift Roll-Over Check:**
If $(Current Time + T_{total}) > S_{end}$, the remaining processing time is added to the start of the next day's shift.

### 3.5. Automated Inventory & Machine Management

* **Consumables Deductions:** Automatically subtracts detergent/softener based on weight.
* *Example Formula:* If 1 kg requires $15$ ml of detergent, an $8$ kg order deducts $120$ ml from master inventory.


* **Low Stock Alerts:** Dashboard alerts owner when consumables drop below a set threshold.
* **Machine Status:** * Status states: Idle, Running (with countdown timer), Maintenance Required.
* Staff can mark a machine "Out of Order" with one click, automatically removing it from the ETA and Bucket allocation pool.



### 3.6. Billing & Payments (No-Accounting Focus)

* **Simplified Checkout:** * Options: Cash, UPI (Scanner/Link via WA), Card.
* **Payment Status:** Just a binary toggle: `Paid` or `Unpaid`. No complex ledgers or double-entry bookkeeping.
* **Loyalty Integration:** Automatically checks if the customer's phone number has points and prompts the staff: "Apply 10% discount?"

---

## 4. Non-Functional Requirements (NFR)

* **Usability (Critical NFR):** * UI must pass the "Thumb Zone" test (essential buttons at the bottom of the screen).
* Colors must be universally understood: Green (Go/Done), Yellow (In Progress), Red (Action Required/Alert).
* Multi-lingual support (e.g., English, Hindi, local regional languages) for staff interfaces.


* **Offline Capability:** The app must be able to log orders offline and sync to the cloud (and trigger WhatsApp messages) once internet is restored, ensuring no downtime during network drops.
* **Performance:** Order tracking updates and bucket state changes must register in under 1 second to prevent staff frustration.

---

## 5. Future Scope (Phase 2)

1. **Driver Module:** Dedicated route-mapping screen for pickup/delivery boys.
2. **Customer App:** Optional self-service app for booking pickups.
3. **Multi-Store Analytics:** For owners expanding to multiple outlets.

---