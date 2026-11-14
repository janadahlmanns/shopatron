"""Overlay tests in a temporary headless Chrome instance on a static page (no shop access)."""

import pytest
from playwright.sync_api import sync_playwright

from shopatron.overlay import Overlay


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page()
        page.set_content("<html><body><h1>Test page</h1></body></html>")
        yield page
        browser.close()


def test_button_click_is_returned_once(page):
    overlay = Overlay(page)
    overlay.show("Speichern?", [("Ja", "yes"), ("Nein", "no")])
    assert overlay.poll() is None
    page.get_by_role("button", name="Nein").click()  # Playwright locators pierce the Shadow DOM
    assert overlay.poll() == "no"
    assert overlay.poll() is None  # an answer is delivered only once


def test_box_is_restored_after_navigation(page):
    overlay = Overlay(page)
    overlay.show("Hallo")
    page.set_content("<html><body>new page</body></html>")  # equivalent to navigation: box removed
    assert page.locator("#shopatron-overlay").count() == 0
    overlay.poll()
    assert page.get_by_text("Hallo").is_visible()


def test_message_is_rendered_as_text_not_html(page):
    overlay = Overlay(page)
    overlay.show("<b>fett</b>")
    assert page.get_by_text("<b>fett</b>").is_visible()


def test_hide_removes_box(page):
    overlay = Overlay(page)
    overlay.show("Hallo")
    overlay.hide()
    assert page.locator("#shopatron-overlay").count() == 0
