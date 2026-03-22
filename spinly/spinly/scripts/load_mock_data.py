"""
Spinly mock data loader — generates 55 Laundry Orders with Job Cards.
Run via: bench --site dev.localhost execute spinly.spinly.scripts.load_mock_data.run

Generates:
  - 5  Draft orders
  - 20 Submitted/active orders with Job Cards in mixed workflow states
  - 30 Delivered orders (paid, historical)
"""
import frappe
from frappe.utils import today, add_days, now_datetime
import random


# ── Seed data ─────────────────────────────────────────────────────────────────

CUSTOMERS = [
    "CUST-00001", "CUST-00002", "CUST-00003", "CUST-00004", "CUST-00005",
    "CUST-00006", "CUST-00007", "CUST-00008", "CUST-00009", "CUST-00010",
    "CUST-00011", "CUST-00012", "CUST-00013", "CUST-00014", "CUST-00015",
]

SERVICES = ["SRV-001", "SRV-002", "SRV-003"]   # Wash&Fold, Wash&Iron, DryClean

GARMENT_TYPES = [
    ("GT-0001", 0.3), ("GT-0002", 0.4), ("GT-0003", 0.6),
    ("GT-0004", 0.5), ("GT-0005", 1.2), ("GT-0006", 0.8),
]  # (garment_type, default_weight_kg)

ALERT_TAGS = ["ATAG-0001", "ATAG-0002", "ATAG-0003"]
PAYMENT_METHODS = ["PMETH-0001", "PMETH-0002", "PMETH-0003"]

WORKFLOW_STATES = ["Sorting", "Washing", "Drying", "Ironing", "Ready"]

INSTRUCTIONS = [
    "", "", "",  # Most orders have no instructions
    "Handle gently", "No machine dry", "Separate whites",
    "Express — needed by evening", "Starch the shirts",
]


def _random_items():
    """Return 1–4 garment rows for an order."""
    count = random.randint(1, 4)
    chosen = random.sample(GARMENT_TYPES, count)
    return [
        {"garment_type": gt, "quantity": random.randint(1, 4), "weight_kg": wt}
        for gt, wt in chosen
    ]


def _random_tags():
    """Return 0–2 alert tags."""
    if random.random() < 0.4:
        return random.sample(ALERT_TAGS, random.randint(1, 2))
    return []


def _create_order(customer, service, order_date, payment_method, instructions=""):
    order = frappe.new_doc("Laundry Order")
    order.customer = customer
    order.service = service
    order.order_date = order_date
    order.payment_method = payment_method
    order.special_instructions = instructions
    for row in _random_items():
        order.append("items", row)
    for tag in _random_tags():
        order.append("alert_tags", {"alert_tag": tag})
    return order


def run():
    frappe.set_user("Administrator")

    # Check if customers exist
    if not frappe.db.exists("Laundry Customer", "CUST-00001"):
        print("ERROR: Customers not loaded. Run bench migrate first to load fixtures.")
        return

    # Check if services exist — get actual service names
    services = frappe.get_all("Laundry Service", fields=["name"], limit=3)
    if not services:
        print("ERROR: Laundry Services not found. Run bench migrate first.")
        return
    svc_names = [s.name for s in services]

    garments = frappe.get_all("Garment Type", filters={"is_active": 1}, fields=["name", "default_weight_kg"])
    if not garments:
        print("ERROR: Garment Types not found.")
        return
    garment_data = [(g.name, g.default_weight_kg or 0.5) for g in garments]

    alert_tags = frappe.get_all("Alert Tag", filters={"is_active": 1}, fields=["name"])
    tag_names = [t.name for t in alert_tags]

    payment_methods = frappe.get_all("Payment Method", filters={"is_active": 1}, fields=["name"])
    pm_names = [p.name for p in payment_methods]

    created = 0

    # ── 30 delivered (historical) orders ─────────────────────────────────────
    print("Creating 30 historical delivered orders...")
    for i in range(30):
        customer = CUSTOMERS[i % len(CUSTOMERS)]
        service = svc_names[i % len(svc_names)]
        days_back = random.randint(2, 60)
        order_date = add_days(today(), -days_back)
        pm = random.choice(pm_names)

        try:
            order = frappe.new_doc("Laundry Order")
            order.customer = customer
            order.service = service
            order.order_date = order_date
            order.payment_method = pm
            order.payment_status = "Paid"
            order.special_instructions = random.choice(INSTRUCTIONS)

            # Add items
            count = random.randint(1, 4)
            chosen = random.sample(garment_data, min(count, len(garment_data)))
            for gt, wt in chosen:
                order.append("items", {"garment_type": gt, "quantity": random.randint(1, 3), "weight_kg": wt})

            # Add tags (40% chance)
            if tag_names and random.random() < 0.4:
                for tag in random.sample(tag_names, random.randint(1, min(2, len(tag_names)))):
                    order.append("alert_tags", {"alert_tag": tag})

            order.insert(ignore_permissions=True)
            order.submit()

            # Advance job card to Delivered state
            jc_name = frappe.db.get_value("Laundry Job Card", {"laundry_order": order.name}, "name")
            if jc_name:
                from frappe.model.workflow import apply_workflow
                jc = frappe.get_doc("Laundry Job Card", jc_name)
                for action in ["Start Washing", "Start Drying", "Start Ironing", "Mark Ready", "Mark Delivered"]:
                    try:
                        apply_workflow(jc, action)
                        jc.reload()
                    except Exception:
                        pass

            created += 1
        except Exception as e:
            print(f"  Skipped delivered order {i+1}: {e}")

    # ── 20 active orders (mixed workflow states) ───────────────────────────────
    print("Creating 20 active orders with mixed Job Card states...")
    workflow_actions_by_state = {
        "Sorting": [],
        "Washing": ["Start Washing"],
        "Drying": ["Start Washing", "Start Drying"],
        "Ironing": ["Start Washing", "Start Drying", "Start Ironing"],
        "Ready": ["Start Washing", "Start Drying", "Start Ironing", "Mark Ready"],
    }

    for i in range(20):
        customer = CUSTOMERS[i % len(CUSTOMERS)]
        service = svc_names[i % len(svc_names)]
        order_date = add_days(today(), -random.randint(0, 3))
        pm = random.choice(pm_names)
        target_state = WORKFLOW_STATES[i % len(WORKFLOW_STATES)]

        try:
            order = frappe.new_doc("Laundry Order")
            order.customer = customer
            order.service = service
            order.order_date = order_date
            order.payment_method = pm
            order.special_instructions = random.choice(INSTRUCTIONS)

            count = random.randint(1, 4)
            chosen = random.sample(garment_data, min(count, len(garment_data)))
            for gt, wt in chosen:
                order.append("items", {"garment_type": gt, "quantity": random.randint(1, 3), "weight_kg": wt})

            if tag_names and random.random() < 0.4:
                for tag in random.sample(tag_names, random.randint(1, min(2, len(tag_names)))):
                    order.append("alert_tags", {"alert_tag": tag})

            order.insert(ignore_permissions=True)
            order.submit()

            # Advance to target state
            jc_name = frappe.db.get_value("Laundry Job Card", {"laundry_order": order.name}, "name")
            if jc_name:
                from frappe.model.workflow import apply_workflow
                jc = frappe.get_doc("Laundry Job Card", jc_name)
                for action in workflow_actions_by_state.get(target_state, []):
                    try:
                        apply_workflow(jc, action)
                        jc.reload()
                    except Exception:
                        pass

            created += 1
        except Exception as e:
            print(f"  Skipped active order {i+1}: {e}")

    # ── 5 draft orders ────────────────────────────────────────────────────────
    print("Creating 5 draft orders...")
    for i in range(5):
        customer = CUSTOMERS[i % 5]
        service = svc_names[i % len(svc_names)]

        try:
            order = frappe.new_doc("Laundry Order")
            order.customer = customer
            order.service = service
            order.order_date = today()
            order.payment_method = pm_names[0] if pm_names else None

            gt, wt = garment_data[i % len(garment_data)]
            order.append("items", {"garment_type": gt, "quantity": random.randint(1, 3), "weight_kg": wt})
            order.insert(ignore_permissions=True)
            # NOT submitted — stays draft
            created += 1
        except Exception as e:
            print(f"  Skipped draft order {i+1}: {e}")

    frappe.db.commit()
    print(f"\n✅ Mock data loaded: {created} orders created.")
    print("   — 30 delivered (historical)")
    print("   — 20 active (mixed Job Card states)")
    print("   —  5 drafts")
