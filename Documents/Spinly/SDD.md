# 📑 Software Design Document: Spinly

**Project:** Spinly Laundry Management System

**Framework:** Frappe Framework (Python/MariaDB/Vue.js)

**App Namespace:** `spinly`

**Status:** Design Phase

---

## 1. System Architecture

Spinly is designed as a **Monolithic Custom App** on top of the Frappe Bench. It leverages Frappe's "DocType" system to automate database schema generation and REST API creation.

### 1.1 Tech Stack

* **Backend:** Python (Frappe Server Side)
* **Database:** MariaDB
* **Frontend:** Vue.js (for the Custom POS Page) & Jinja2 (for Print Formats)
* **Background Jobs:** Redis/Python RQ (for WhatsApp triggers)

---

## 2. Data Model (DocTypes)

### 2.1 Master DocTypes

| DocType | Naming | Description |
| --- | --- | --- |
| **Laundry Customer** | `CUST-.#####` | Lightweight CRM (Phone, Name, Loyalty Points). |
| **Laundry Service** | `SRV-.###` | Service catalog (e.g., Wash & Fold) with base pricing and processing time. |
| **Laundry Machine** | `MAC-.##` | Machine master. Includes `capacity_kg` and current `status`. |
| **Laundry Consumable** | `CONS-.###` | Inventory items (Detergent, Softener) with `consumption_per_kg` ratio. |
| **Spinly Settings** | `Single` | Global config: Shift timings (10 hrs), WhatsApp API keys, UPI ID. |

### 2.2 Transactional DocTypes

| DocType | Naming | Description |
| --- | --- | --- |
| **Laundry Order** | `ORD-.YYYY.-.#####` | The main bill. Submittable. Links to items and customer. |
| **Laundry Job Card** | `JOB-.YYYY.-.#####` | Internal bucket tracking. Tracks the workflow state. |

---

## 3. Core Logic & Formulas

### 3.1 Dynamic ETA Calculation

The ETA is calculated during the `validate` trigger of a `Laundry Order`.

**The Formula:**


$$ETA = T_{now} + T_{queue} + T_{service}$$

Where:

* $T_{queue}$: The sum of remaining time for all jobs currently assigned to the target machine.
* $T_{service}$: The base time defined in the **Laundry Service** master.
* **Shift Logic:** If $ETA > Shift\_End$, the system adds the difference to the $Shift\_Start$ of the next calendar day.

### 3.2 Auto-Inventory Deduction

Triggered on `on_submit` of the **Laundry Job Card**:

* `Deduction Qty = Order Weight (kg) × Consumable Ratio (ml/kg)`
* This uses the `frappe.db.set_value` to decrement the `current_stock` in the **Laundry Consumable** master automatically.

---

## 4. Feature Modules

### 4.1 "Blue-Collar" POS Page (Custom UI)

Standard Frappe forms are too data-heavy. We will implement a **Custom Page** (`spinly_pos`) using Vue.js.

* **Keypad Input:** Large buttons for phone number entry.
* **Icon Grid:** Visual selection for garment types (Shirts, Bedding, etc.).
* **One-Touch Alerts:** Large toggle buttons for "Whites," "Colored," or "Delicates."
* **Direct Print:** Uses `frappe.utils.print_format` to trigger a thermal printer immediately upon order save.

### 4.2 Internal Bucket Tracking (The "Internal Bill")

Every order generates a **Job Card**.

* **Bucket ID:** A large-font ID for physical tagging.
* **Workflow Steps:** Sorting → Washing → Drying → Ironing → Ready.
* **Internal Instructions:** Fetches "Customer Comments" and "Machine Assignment" based on available load.

---

## 5. Integration & Notifications

### 5.1 WhatsApp Workflow

We will use a custom Python module `whatsapp_handler.py`.

1. **Order Confirmation:** Sent on `on_submit` of `Laundry Order`. Includes a link to the digital receipt.
2. **Pickup Reminder:** Sent when `Laundry Job Card` status changes to "Ready."
3. **UPI Link:** Dynamically generated using the `total_amount` and the UPI ID from **Spinly Settings**.

### 5.2 Two-Way Billing (Print Formats)

* **Customer Invoice:** Focuses on Price, Count, and ETA. Includes a QR code for payment.
* **Internal Job Tag:** Focuses on Machine #, Lot ID, and Special Warnings (e.g., "Hand Wash Only").

---

## 6. Implementation Plan (The "Bench" Way)

### Phase 1: Setup

```bash
bench new-app spinly
bench install-app spinly

```

### Phase 2: Python Hooks (`hooks.py`)

```python
# Map the logic to Document events
doc_events = {
    "Laundry Order": {
        "before_save": "spinly.logic.eta_calc.calculate",
        "after_insert": "spinly.integrations.whatsapp.send_receipt"
    },
    "Laundry Job Card": {
        "on_submit": "spinly.logic.inventory.deduct_stock"
    }
}

```

### Phase 3: The Custom Page

Create `spinly/public/js/spinly_pos.vue` to handle the high-speed intake UI.

---

## 7. Roles & Permissions

* **Laundry Staff:** Access to `Laundry Order` (Create/Read), `Job Card` (Update Status). Redirected to POS Page on login.
* **System Manager:** Full access to Settings, Inventory, and Dashboards.

---