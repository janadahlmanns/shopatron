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


def test_close_button_hides_box(page):
    overlay = Overlay(page)
    overlay.show("Fertig", closable=True)
    page.get_by_role("button", name="Schließen").click()
    assert not page.get_by_text("Fertig").is_visible()
    assert overlay.poll() == "close"
    assert not page.get_by_text("Fertig").is_visible()  # stays hidden on later polls


def test_no_close_button_by_default(page):
    overlay = Overlay(page)
    overlay.show("Bitte auswählen", [("Überspringen", "skip")])
    assert page.get_by_role("button", name="Schließen").count() == 0


def test_long_message_scrolls_inside_box(page):
    page.set_viewport_size({"width": 1200, "height": 600})
    overlay = Overlay(page)
    overlay.show("\n".join(f"Zeile {i}" for i in range(200)), closable=True)
    box_height = page.locator(".box").bounding_box()["height"]
    assert box_height < 600 * 0.75


def test_hide_removes_box(page):
    overlay = Overlay(page)
    overlay.show("Hallo")
    overlay.hide()
    assert page.locator("#shopatron-overlay").count() == 0
