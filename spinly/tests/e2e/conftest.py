"""
Spinly POS E2E Test Configuration
"""
import os
import pytest
from playwright.sync_api import Page, BrowserContext, Browser, sync_playwright

BASE_URL = os.environ.get("SPINLY_TEST_URL", "http://dev.localhost:8000")
ADMIN_USER = os.environ.get("SPINLY_TEST_USER", "Administrator")
ADMIN_PASS = os.environ.get("SPINLY_TEST_PASS", "admin123")


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture(scope="session")
def browser_context(browser: Browser):
    """Single browser context reused across the session to share auth cookies."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844},   # iPhone 14 — matches POS target device
    )
    # Log in once, persist cookies across all tests
    page = context.new_page()
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("domcontentloaded")
    page.fill("#login_email", ADMIN_USER)
    page.fill("#login_password", ADMIN_PASS)
    # Try different login button selectors across Frappe versions
    for sel in [".btn-login", "button[type='submit']", "[data-label='Login']"]:
        btn = page.locator(sel)
        if btn.count() > 0:
            btn.first.click()
            break
    page.wait_for_url("**/desk**", timeout=20_000)
    page.close()
    yield context
    context.close()


@pytest.fixture
def page(browser_context: BrowserContext):
    """Fresh page per test, but shared auth session."""
    p = browser_context.new_page()
    yield p
    p.close()

