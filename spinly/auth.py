import frappe


def redirect_staff_to_pos(login_manager):
    """Redirect Laundry Staff to the POS page on login."""
    user = login_manager.user
    roles = frappe.get_roles(user)
    if "Laundry Staff" in roles and "System Manager" not in roles:
        frappe.local.response["home_page"] = "/spinly-pos"
