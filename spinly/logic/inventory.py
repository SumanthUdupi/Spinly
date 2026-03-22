"""
Consumable inventory management — restock and low-stock alerts.
"""
import frappe


def on_restock(doc, method=None):
    """Update consumable stock after a restock log is inserted."""
    consumable = frappe.get_doc("Laundry Consumable", doc.consumable)
    stock_before = consumable.current_stock or 0
    consumable.current_stock = stock_before + (doc.quantity_added or 0)
    consumable.save(ignore_permissions=True)

    doc.db_set("stock_before", stock_before)
    doc.db_set("stock_after", consumable.current_stock)


def check_low_stock():
    """Daily job: send alert email for consumables below reorder threshold."""
    low = frappe.db.sql(
        """SELECT name, item_name, current_stock, reorder_threshold
           FROM `tabLaundry Consumable`
           WHERE is_active=1 AND current_stock < reorder_threshold""",
        as_dict=True,
    )
    if not low:
        return

    settings = frappe.get_cached_doc("Spinly Settings")
    alert_email = settings.low_stock_alert_email
    if not alert_email:
        return

    lines = "\n".join(
        f"  • {r.item_name}: {r.current_stock} (threshold: {r.reorder_threshold})"
        for r in low
    )
    frappe.sendmail(
        recipients=[alert_email],
        subject="Spinly — Low Stock Alert",
        message=f"The following consumables are below reorder threshold:\n\n{lines}",
    )


def deduct_for_order(order):
    """Deduct consumable stock proportional to order weight."""
    weight = order.total_weight_kg or 0
    if weight <= 0:
        return

    consumables = frappe.get_all(
        "Laundry Consumable",
        filters={"is_active": 1},
        fields=["name", "consumption_per_kg", "current_stock"],
    )
    for c in consumables:
        deduction = (c.consumption_per_kg or 0) * weight
        new_stock = max(0, (c.current_stock or 0) - deduction)
        frappe.db.set_value("Laundry Consumable", c.name, "current_stock", new_stock)


def restore_for_order(order):
    """Restore consumable stock when an order is cancelled."""
    weight = order.total_weight_kg or 0
    if weight <= 0:
        return

    consumables = frappe.get_all(
        "Laundry Consumable",
        filters={"is_active": 1},
        fields=["name", "consumption_per_kg", "current_stock"],
    )
    for c in consumables:
        restock = (c.consumption_per_kg or 0) * weight
        new_stock = (c.current_stock or 0) + restock
        frappe.db.set_value("Laundry Consumable", c.name, "current_stock", new_stock)
