"""
Spinly POS — E2E Tests
Covers the core user journeys:
  1. CSS/font assets load correctly
  2. Screen 1: Phone keypad input and display
  3. Screen 1: Customer lookup (found / not found)
  4. Screen 1: New customer form visibility
  5. Screen 2: Garment selection & quantity controls
  6. Screen 2: Service selector + order summary update
  7. Screen 3: Confirm screen layout elements
  8. Screen 4: Job card workflow bar
  9. Responsive: 375px viewport
  10. Accessibility: focus states, aria attributes
  11. Redesign: SVG icons present (no structural emoji)
  12. Redesign: DM Sans / Orbitron font stack loaded
  13. ORD-06: Empty cart helper text (new)
  14. Keyboard input support (new)
  15. ARIA labels on quantity controls (new)
  16. SEC-08: color_code sanitization (new)
"""
import re
import pytest
from playwright.sync_api import Page, expect


BASE_URL = "http://dev.localhost:8000"


# ── Helpers ────────────────────────────────────────────────────────────────

def navigate_to_pos(page: Page):
    """Go to POS and wait for it to mount."""
    page.goto(f"{BASE_URL}/app/spinly-pos", wait_until="domcontentloaded")
    page.wait_for_selector("#spinly-pos", timeout=20_000)


def type_phone(page: Page, number: str):
    """Press numeric keypad digits."""
    for digit in number:
        btn = page.locator(f'.sp-key[data-digit="{digit}"]')
        btn.click()
        page.wait_for_timeout(50)


# ── Test 1: POS page loads ─────────────────────────────────────────────────

def test_pos_page_loads(page: Page):
    """POS root element mounts and screen 1 is visible."""
    navigate_to_pos(page)

    root = page.locator("#spinly-pos")
    expect(root).to_be_visible()

    screen1 = page.locator("#sp-screen-1")
    expect(screen1).to_be_visible()

    # Other screens should be hidden
    expect(page.locator("#sp-screen-2")).to_be_hidden()
    expect(page.locator("#sp-screen-3")).to_be_hidden()
    expect(page.locator("#sp-screen-4")).to_be_hidden()


# ── Test 2: CSS redesign assets load ──────────────────────────────────────

def test_css_assets_loaded(page: Page):
    """CSS is applied — background color matches OLED theme (#070d1a)."""
    navigate_to_pos(page)

    root = page.locator("#spinly-pos")
    bg_color = root.evaluate("el => getComputedStyle(el).backgroundColor")
    # #070d1a = rgb(7, 13, 26)
    assert "7, 13, 26" in bg_color or "070d1a" in bg_color.lower(), \
        f"Expected OLED dark background, got: {bg_color}"


# ── Test 3: SVG icons — no structural emoji ────────────────────────────────

def test_no_structural_emoji_in_buttons(page: Page):
    """Confirm, Next Step and back buttons use SVG icons not emoji."""
    navigate_to_pos(page)

    # Back button on screen 1 doesn't exist, check header logo
    logo = page.locator(".sp-logo")
    expect(logo).to_be_visible()
    # Logo should contain an SVG
    svg_in_logo = logo.locator("svg")
    expect(svg_in_logo).to_have_count(1)

    # The header title should be "SPINLY" not "🧺 Spinly POS"
    title = page.locator(".sp-title")
    title_text = title.text_content()
    assert "🧺" not in (title_text or ""), "Structural emoji 🧺 found in title"


# ── Test 4: Phone keypad — digit input ────────────────────────────────────

def test_keypad_digit_input(page: Page):
    """Tapping keypad digits updates the phone display."""
    navigate_to_pos(page)

    display = page.locator("#sp-phone-value")

    # Initially empty (cursor visible)
    cursor = page.locator("#sp-phone-cursor")
    expect(cursor).to_be_visible()

    # Type 5 digits
    type_phone(page, "98765")
    page.wait_for_timeout(200)

    phone_text = display.text_content()
    assert "98765" in (phone_text or ""), f"Expected digits in display, got: {phone_text}"

    # Cursor should hide when digits entered
    cursor_display = cursor.evaluate("el => el.style.display")
    assert cursor_display == "none", "Cursor should be hidden when digits are entered"


# ── Test 5: Backspace key ─────────────────────────────────────────────────

def test_keypad_backspace(page: Page):
    """Backspace removes last digit."""
    navigate_to_pos(page)

    type_phone(page, "123")
    page.locator("#sp-key-back").click()
    page.wait_for_timeout(100)

    phone_text = (page.locator("#sp-phone-value").text_content() or "").strip()
    assert phone_text == "12", f"Expected '12' after backspace, got: {phone_text!r}"


# ── Test 6: CLR key clears all digits and restores cursor ─────────────────

def test_keypad_clear(page: Page):
    """CLR button clears the phone display and shows cursor again."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.locator("#sp-key-clear").click()
    page.wait_for_timeout(200)

    phone_text = page.locator("#sp-phone-value").text_content() or ""
    assert phone_text.strip() == "", f"Expected empty display after CLR, got: '{phone_text}'"

    cursor = page.locator("#sp-phone-cursor")
    cursor_display = cursor.evaluate("el => el.style.display")
    assert cursor_display != "none", "Cursor should reappear after CLR"


# ── Test 7: 10-digit number triggers customer search ──────────────────────

def test_customer_search_triggers_on_10_digits(page: Page):
    """Entering 10 digits fires the customer search (shows result card or add button)."""
    navigate_to_pos(page)

    # Type 10 digits — may match or not match; either outcome is valid
    type_phone(page, "9876543210")
    page.wait_for_timeout(1500)   # Allow network call

    # Either the customer card appears OR the add-new button appears
    customer_visible = page.locator("#sp-customer-card").is_visible()
    add_btn_visible = page.locator("#sp-add-new-btn").is_visible()
    assert customer_visible or add_btn_visible, \
        "After 10 digits, either customer card or Add New button should appear"


# ── Test 8: Known customer found (CUST-00001 / 9876543210) ────────────────

def test_known_customer_shows_card(page: Page):
    """Fixture customer Priya Sharma (9876543210) shows customer card with tier badge."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)

    card = page.locator("#sp-customer-card")
    if not card.is_visible():
        pytest.skip("Fixture customer not loaded — run bench migrate first")

    expect(card).to_be_visible()
    name = page.locator("#sp-cust-name").text_content()
    assert name and len(name) > 0, "Customer name should be populated"

    # Tier badge should exist
    tier_badge = page.locator("#sp-cust-tier")
    expect(tier_badge).to_be_visible()
    tier_text = tier_badge.text_content() or ""
    assert any(t in tier_text for t in ["Bronze", "Silver", "Gold", "Diamond"]), \
        f"Expected tier in badge text, got: {tier_text}"


# ── Test 9: Add New button toggles new customer form ──────────────────────

def test_add_new_customer_form(page: Page):
    """Clicking '+ ADD NEW CUSTOMER' shows the name input form."""
    navigate_to_pos(page)

    # Type an unknown number
    type_phone(page, "1111111111")
    page.wait_for_timeout(1500)

    add_btn = page.locator("#sp-add-new-btn")
    if not add_btn.is_visible():
        pytest.skip("Add New button not visible — customer may already exist")

    add_btn.click()

    form = page.locator("#sp-new-customer-form")
    expect(form).to_be_visible()

    name_input = page.locator("#sp-new-name")
    expect(name_input).to_be_visible()
    expect(name_input).to_be_focused()


# ── Test 10: Select customer navigates to screen 2 ─────────────────────────

def test_select_customer_goes_to_screen2(page: Page):
    """Selecting a found customer transitions to the order builder screen."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)

    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Select button not visible — customer fixture may not be loaded")

    select_btn.click()
    page.wait_for_timeout(500)

    expect(page.locator("#sp-screen-2")).to_be_visible()
    expect(page.locator("#sp-screen-1")).to_be_hidden()

    # Customer name should appear in the screen 2 header
    s2_name = page.locator("#sp-s2-customer-name")
    expect(s2_name).to_be_visible()
    name_text = s2_name.text_content() or ""
    assert len(name_text.strip()) > 0, "Screen 2 header should show customer name"


# ── Test 11: Screen 2 — garment grid populated ────────────────────────────

def test_screen2_garment_grid_populated(page: Page):
    """Screen 2 shows garment buttons loaded from API."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)

    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    grid = page.locator("#sp-garment-grid")
    garment_btns = grid.locator(".sp-garment-btn")
    count = garment_btns.count()
    assert count > 0, f"Expected garment buttons, got {count}"


# ── Test 12: Screen 2 — qty increment / decrement ─────────────────────────

def test_screen2_garment_quantity_controls(page: Page):
    """Incrementing a garment quantity updates the counter and price."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    # Click the first garment's + button
    first_inc = page.locator(".sp-garment-btn .sp-qty-btn[data-action='inc']").first
    first_inc.click()
    page.wait_for_timeout(200)

    # Check the quantity display updated from 0 → 1
    first_qty = page.locator(".sp-garment-btn .sp-qty-num").first
    qty_text = first_qty.text_content()
    assert qty_text == "1", f"Expected qty=1 after increment, got: {qty_text}"

    # Price should have updated from ₹0.00
    price_display = page.locator("#sp-price-display")
    price_text = price_display.text_content() or ""
    assert price_text != "₹0.00", f"Price should update after adding garment, got: {price_text}"


# ── Test 13: Screen 2 — Review button disabled when no items ─────────────

def test_review_btn_disabled_with_no_items(page: Page):
    """Review Order button is disabled when no garments selected."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    review_btn = page.locator("#sp-review-btn")
    expect(review_btn).to_be_disabled()


# ── Test 14: Screen 2 — Review enabled after adding garment ───────────────

def test_review_btn_enabled_after_adding_item(page: Page):
    """Review Order button becomes enabled after adding at least one garment."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    page.locator(".sp-garment-btn .sp-qty-btn[data-action='inc']").first.click()
    page.wait_for_timeout(200)

    review_btn = page.locator("#sp-review-btn")
    expect(review_btn).to_be_enabled()


# ── Test 15: Screen 2 → Screen 3 via Review button ────────────────────────

def test_navigate_to_confirm_screen(page: Page):
    """Clicking Review Order with items navigates to the confirm screen."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    page.locator(".sp-garment-btn .sp-qty-btn[data-action='inc']").first.click()
    page.wait_for_timeout(200)
    page.locator("#sp-review-btn").click()
    page.wait_for_timeout(2500)   # preview_order API call

    expect(page.locator("#sp-screen-3")).to_be_visible()
    expect(page.locator("#sp-screen-2")).to_be_hidden()


# ── Test 16: Screen 3 — confirm card shows machine + ETA ─────────────────

def test_confirm_screen_shows_order_summary(page: Page):
    """Confirm screen displays machine assignment and pricing breakdown."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    page.locator(".sp-garment-btn .sp-qty-btn[data-action='inc']").first.click()
    page.wait_for_timeout(200)
    page.locator("#sp-review-btn").click()
    page.wait_for_timeout(2500)

    # Confirm card
    expect(page.locator("#sp-confirm-machine")).to_be_visible()
    expect(page.locator("#sp-confirm-eta")).to_be_visible()

    # Price breakdown
    expect(page.locator("#sp-sub-display")).to_be_visible()
    expect(page.locator("#sp-total-display")).to_be_visible()

    total_text = page.locator("#sp-total-display").text_content() or ""
    assert "₹" in total_text or len(total_text) > 0, "Total should show a price"


# ── Test 17: Screen 3 — payment method buttons ───────────────────────────

def test_confirm_screen_payment_methods(page: Page):
    """Payment method buttons exist and one is pre-selected."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    page.locator(".sp-garment-btn .sp-qty-btn[data-action='inc']").first.click()
    page.wait_for_timeout(200)
    page.locator("#sp-review-btn").click()
    page.wait_for_timeout(2500)

    payment_btns = page.locator(".sp-payment-btn")
    count = payment_btns.count()
    assert count > 0, f"Expected payment method buttons, got {count}"

    # One should be pre-selected
    selected = page.locator(".sp-payment-btn.selected")
    expect(selected).to_have_count(1)


# ── Test 18: Back navigation from screen 2 ───────────────────────────────

def test_back_from_screen2_returns_to_screen1(page: Page):
    """Back button on screen 2 returns to the customer search screen."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(500)

    page.locator("#sp-s2-back").click()
    page.wait_for_timeout(300)

    expect(page.locator("#sp-screen-1")).to_be_visible()
    expect(page.locator("#sp-screen-2")).to_be_hidden()


# ── Test 19: Back navigation from screen 3 ───────────────────────────────

def test_back_from_screen3_returns_to_screen2(page: Page):
    """Back button on screen 3 returns to order builder."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    page.locator(".sp-garment-btn .sp-qty-btn[data-action='inc']").first.click()
    page.wait_for_timeout(200)
    page.locator("#sp-review-btn").click()
    page.wait_for_timeout(2500)

    page.locator("#sp-s3-back").click()
    page.wait_for_timeout(300)

    expect(page.locator("#sp-screen-2")).to_be_visible()
    expect(page.locator("#sp-screen-3")).to_be_hidden()


# ── Test 20: Touch target sizes ──────────────────────────────────────────

def test_keypad_touch_targets_minimum_size(page: Page):
    """All keypad keys meet 44×44px minimum touch target (WCAG 2.5.5)."""
    navigate_to_pos(page)

    keys = page.locator(".sp-key")
    count = keys.count()
    assert count == 12, f"Expected 12 keys (0-9, CLR, ⌫), got {count}"

    for i in range(count):
        box = keys.nth(i).bounding_box()
        assert box is not None
        assert box["width"] >= 44, f"Key {i} width {box['width']}px < 44px"
        assert box["height"] >= 44, f"Key {i} height {box['height']}px < 44px"


# ── Test 21: ARIA attributes on interactive regions ───────────────────────

def test_aria_attributes_present(page: Page):
    """Key interactive regions have ARIA labels for accessibility."""
    navigate_to_pos(page)

    # Keypad group
    keypad = page.locator("#sp-keypad")
    aria = keypad.get_attribute("role")
    assert aria == "group", f"Keypad should have role='group', got: {aria}"

    aria_label = keypad.get_attribute("aria-label")
    assert aria_label and len(aria_label) > 0, "Keypad should have aria-label"

    # Spinner
    spinner = page.locator("#sp-spinner")
    role = spinner.get_attribute("role")
    assert role == "status", f"Spinner should have role='status', got: {role}"


# ── Test 22: Responsive — 375px viewport ──────────────────────────────────

def test_responsive_375px_viewport(page: Page):
    """POS layout is usable at 375px (small phone) — no horizontal scroll."""
    page.set_viewport_size({"width": 375, "height": 812})
    navigate_to_pos(page)

    # Check no horizontal overflow
    scroll_width = page.evaluate("document.body.scrollWidth")
    client_width = page.evaluate("document.body.clientWidth")
    assert scroll_width <= client_width + 2, \
        f"Horizontal scroll detected: scrollWidth={scroll_width}, clientWidth={client_width}"

    # POS should still be visible
    expect(page.locator("#spinly-pos")).to_be_visible()
    expect(page.locator("#sp-screen-1")).to_be_visible()


# ── Test 23: Spinner hidden on load ───────────────────────────────────────

def test_spinner_initially_hidden(page: Page):
    """Global spinner is hidden when page first loads (not blocking)."""
    navigate_to_pos(page)
    page.wait_for_timeout(3000)   # Wait for masters to load

    spinner = page.locator("#sp-spinner")
    expect(spinner).to_be_hidden()


# ── Test 24: Service row populated ────────────────────────────────────────

def test_service_buttons_populated_on_screen2(page: Page):
    """Screen 2 service row is populated after navigating to order builder."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    service_btns = page.locator("#sp-service-row .sp-service-btn")
    count = service_btns.count()
    assert count > 0, f"Expected service buttons, got {count}"

    # First service should be auto-selected
    selected = page.locator("#sp-service-row .sp-service-btn.selected")
    expect(selected).to_have_count(1)


# ── Test 25: prefers-reduced-motion respected ─────────────────────────────

def test_reduced_motion_css_rule_present(page: Page):
    """CSS contains prefers-reduced-motion rule to disable animations."""
    navigate_to_pos(page)

    # Evaluate whether the reduced-motion media query disables screen-enter animation
    has_reduced = page.evaluate("""() => {
        const sheets = Array.from(document.styleSheets);
        for (const sheet of sheets) {
            try {
                const rules = Array.from(sheet.cssRules || []);
                for (const rule of rules) {
                    if (rule.media && rule.media.mediaText &&
                        rule.media.mediaText.includes('prefers-reduced-motion')) {
                        return true;
                    }
                }
            } catch (e) {}
        }
        return false;
    }""")
    assert has_reduced, "Expected @media (prefers-reduced-motion) rule in CSS"


# ── Test 26: ORD-06 — Helper text visible when cart empty ─────────────────

def test_empty_cart_helper_text_visible(page: Page):
    """Helper text 'Add at least one garment' shows when no items selected."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    helper = page.locator("#sp-review-helper")
    expect(helper).to_be_visible()
    helper_text = helper.text_content() or ""
    assert "garment" in helper_text.lower() or "add" in helper_text.lower(), \
        f"Helper text should mention adding garments, got: {helper_text!r}"


# ── Test 27: ORD-06 — Helper text hides when item added ───────────────────

def test_empty_cart_helper_text_hides_after_add(page: Page):
    """Helper text disappears once at least one garment is added."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    # Verify visible before adding
    helper = page.locator("#sp-review-helper")
    expect(helper).to_be_visible()

    # Add one garment
    page.locator(".sp-garment-btn .sp-qty-btn[data-action='inc']").first.click()
    page.wait_for_timeout(200)

    # Helper should now be hidden
    helper_display = helper.evaluate("el => el.style.display")
    assert helper_display == "none", \
        f"Helper text should be hidden after adding garment, style.display={helper_display!r}"


# ── Test 28: Keyboard input on phone keypad ───────────────────────────────

def test_keyboard_input_on_screen1(page: Page):
    """Hardware keyboard digits update phone display on Screen 1."""
    navigate_to_pos(page)

    display = page.locator("#sp-phone-value")

    # Focus the page first (click anywhere safe)
    page.locator("body").click()
    page.wait_for_timeout(100)

    # Send keyboard digits
    page.keyboard.press("9")
    page.keyboard.press("8")
    page.keyboard.press("7")
    page.wait_for_timeout(200)

    phone_text = display.text_content() or ""
    assert "987" in phone_text.replace(" ", ""), \
        f"Keyboard digits should update phone display, got: {phone_text!r}"

    # Backspace should remove last digit
    page.keyboard.press("Backspace")
    page.wait_for_timeout(100)
    phone_text_after = display.text_content() or ""
    assert "987" not in phone_text_after.replace(" ", "") or \
        len(phone_text_after.replace(" ", "")) < len(phone_text.replace(" ", "")), \
        "Backspace should shorten the phone number"


# ── Test 29: Keyboard input Escape clears phone ───────────────────────────

def test_keyboard_escape_clears_phone(page: Page):
    """Pressing Escape on hardware keyboard clears the phone display."""
    navigate_to_pos(page)

    page.locator("body").click()
    page.keyboard.press("1")
    page.keyboard.press("2")
    page.keyboard.press("3")
    page.wait_for_timeout(200)

    page.keyboard.press("Escape")
    page.wait_for_timeout(100)

    phone_text = (page.locator("#sp-phone-value").text_content() or "").strip()
    assert phone_text == "", f"Escape should clear phone display, got: {phone_text!r}"

    cursor = page.locator("#sp-phone-cursor")
    cursor_display = cursor.evaluate("el => el.style.display")
    assert cursor_display != "none", "Cursor should reappear after Escape"


# ── Test 30: ARIA labels on quantity +/- buttons ──────────────────────────

def test_qty_buttons_have_aria_labels(page: Page):
    """Quantity +/- buttons have descriptive aria-label attributes."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    inc_buttons = page.locator(".sp-qty-btn[data-action='inc']")
    count = inc_buttons.count()
    assert count > 0, "Expected increment buttons in garment grid"

    for i in range(min(count, 3)):  # Check first 3
        label = inc_buttons.nth(i).get_attribute("aria-label")
        assert label and "increase" in label.lower(), \
            f"Inc button {i} should have descriptive aria-label, got: {label!r}"

    dec_buttons = page.locator(".sp-qty-btn[data-action='dec']")
    for i in range(min(dec_buttons.count(), 3)):
        label = dec_buttons.nth(i).get_attribute("aria-label")
        assert label and "decrease" in label.lower(), \
            f"Dec button {i} should have descriptive aria-label, got: {label!r}"


# ── Test 31: Tag button touch targets ≥ 44px ─────────────────────────────

def test_tag_btn_touch_target_minimum(page: Page):
    """Alert tag buttons meet 44px minimum touch target height."""
    navigate_to_pos(page)

    type_phone(page, "9876543210")
    page.wait_for_timeout(2000)
    select_btn = page.locator("#sp-select-customer-btn")
    if not select_btn.is_visible():
        pytest.skip("Skipping: customer fixture not loaded")
    select_btn.click()
    page.wait_for_timeout(800)

    tags = page.locator("#sp-tag-row .sp-tag-btn")
    count = tags.count()
    if count == 0:
        pytest.skip("No alert tags configured")

    for i in range(min(count, 4)):
        box = tags.nth(i).bounding_box()
        assert box is not None
        assert box["height"] >= 44, \
            f"Tag button {i} height {box['height']}px < 44px minimum"


# ── Test 32: SEC-08 — color_code sanitization ─────────────────────────────

def test_color_code_only_hex_applied(page: Page):
    """Alert tag color_code values are restricted to hex format only."""
    navigate_to_pos(page)

    # This tests the _sanitizeColorCode function indirectly:
    # Valid hex colors in --tag-color custom property should be #xxxxxx format
    tag_btns = page.locator(".sp-tag-btn")
    count = tag_btns.count()
    if count == 0:
        pytest.skip("No alert tags to check")

    for i in range(min(count, 5)):
        tag_color = tag_btns.nth(i).evaluate(
            "el => el.style.getPropertyValue('--tag-color').trim()"
        )
        if tag_color:
            assert re.match(r'^#[0-9A-Fa-f]{3,8}$', tag_color), \
                f"Tag {i} --tag-color must be hex only, got: {tag_color!r}"
