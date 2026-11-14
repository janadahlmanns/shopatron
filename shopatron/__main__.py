"""Shopatron command-line interface.

    .venv\\Scripts\\python.exe -m shopatron              list input via terminal, terminated by an empty line
    .venv\\Scripts\\python.exe -m shopatron <file>       list input from a UTF-8 text file
    .venv\\Scripts\\python.exe -m shopatron --defaults   listing of all stored default products

Processing per list entry:
- Entry with a stored default product: the product is added to the cart directly.
- Entry without a default, unavailable default, or choose marker ("?", see shoplist.py):
  the shop's search results page opens for manual selection. The selected product is
  detected via the cart change, its quantity is adjusted to the list quantity, and an
  in-page dialog offers to store it as the new default.

Checkout is never performed; the cart is left for manual review and ordering.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from .db import ItemDB
from .overlay import POLL_MS, Overlay
from .rewe import Product, ReweError, ReweShop
from .shoplist import Entry, parse_list


def read_list_interactively() -> str:
    print("Einkaufsliste eingeben (ein Artikel pro Zeile, z.B. '3 Zwiebeln'). Leere Zeile = fertig.")
    lines = []
    while (line := input("> ")).strip():
        lines.append(line)
    return "\n".join(lines)


def pick_in_browser(shop: ReweShop, overlay: Overlay, entry: Entry, current_default: str | None) -> Product | None:
    """Open the shop's search page and block until a product is added to the cart or the entry is skipped."""
    shop.take_user_adds()  # discard cart changes that occurred before this point
    shop.open_search_page(entry.name)
    message = f"Bitte das passende Produkt für »{entry.name}« ({entry.quantity}×) in den Warenkorb legen.\n"
    if current_default:
        message += f"Bisheriger Standard: {current_default}\n"
    overlay.show(message + "Du kannst auch oben selbst anders suchen.", [("Überspringen", "skip")])
    print("  -> bitte im Browser auswählen ...")
    while True:
        if overlay.poll() == "skip":
            return None
        added = shop.take_user_adds()
        if added:
            return added[0]
        shop.wait(POLL_MS)


def handle_entry(shop: ReweShop, overlay: Overlay, db: ItemDB, entry: Entry) -> str:
    """Process one list entry. Returns a one-line result for the summary."""
    print(f"\n=== {entry.quantity} x {entry.name}" + ("  (selbst auswählen)" if entry.choose else ""))
    item = db.get(entry.name)
    product = None

    if item and item.product_id and not entry.choose:
        product = shop.lookup(item.product_id)
        if product:
            overlay.show(f"Lege {entry.quantity}× {product.title} in den Warenkorb ...")
            total = shop.add(product, entry.quantity)
            print(f"  Standardprodukt: im Warenkorb {total} x {product.title}")
            return f"+{entry.quantity:<3} {product.title}  (jetzt {total} im Warenkorb)"
        print(f"  Standardprodukt '{item.product_title}' ist gerade nicht verfügbar -> Suche")

    before = dict(shop.cart)  # cart state prior to manual selection
    current_default = item.product_title if item and item.product_id else None
    product = pick_in_browser(shop, overlay, entry, current_default)
    if product is None:
        print("  übersprungen")
        return f"ÜBERSPRUNGEN  {entry.name}"

    # The shop's add button adds a single unit; the remainder up to the list quantity is added here.
    target = before.get(product.product_id, 0) + entry.quantity
    total = shop.cart.get(product.product_id, 0)
    if total < target:
        overlay.show(f"Erhöhe auf {target}× {product.title} ...")
        total = shop.set_quantity(product, target)
    print(f"  ausgewählt: im Warenkorb {total} x {product.title}")

    if not item or item.product_id != product.product_id:
        question = f"»{product.title}« als Standard für »{entry.name}« speichern?"
        if current_default:
            question += f"\n(ersetzt: {current_default})\n»Nein« = nur dieses Mal."
        answer = overlay.ask(question, [("Ja, speichern", "yes"), ("Nein", "no")])
        if answer == "yes":
            db.set_default(entry.name, product.product_id, product.title)
            print("  als Standard gespeichert")

    return f"+{total - before.get(product.product_id, 0):<3} {product.title}  (jetzt {total} im Warenkorb)"


def show_defaults(db: ItemDB) -> None:
    items = db.all()
    if not items:
        print("Noch keine Standardprodukte gespeichert.")
    for item in items:
        print(f"{item.name:<30} -> {item.product_title or '-'}  ({item.product_id or 'kein Standard'})")


def main(argv: list[str]) -> int:
    db = ItemDB()
    try:
        if argv and argv[0] == "--defaults":
            show_defaults(db)
            return 0

        text = Path(argv[0]).read_text(encoding="utf-8") if argv else read_list_interactively()
        entries = parse_list(text)
        if not entries:
            print("Leere Liste - nichts zu tun.")
            return 0

        summary = []
        with sync_playwright() as playwright:
            shop = ReweShop.connect(playwright)
            overlay = Overlay(shop.page)
            print(f"Verbunden. Markt {shop.market_id} ({shop.service_type}), "
                  f"{sum(shop.cart.values())} Artikel schon im Warenkorb.")
            try:
                for entry in entries:
                    summary.append(handle_entry(shop, overlay, db, entry))
            except KeyboardInterrupt:
                summary.append("ABGEBROCHEN (Strg+C) - Rest der Liste nicht bearbeitet")

            shop.read_cart()  # leaves the cart page open for manual review
            overlay.show("Fertig! ✓ Bereit zur Prüfung und Bestellung.\n\n" + "\n".join(summary))

        print("\n===== Zusammenfassung =====")
        for line in summary:
            print(line)
        print("\nBitte den Warenkorb im Browser prüfen - bestellt wird von Hand. :-)")
        return 0
    except ReweError as exc:
        print(f"\nFEHLER: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
