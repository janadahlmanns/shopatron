"""Client for the REWE web shop. All site-specific knowledge is confined to this module.

Operates on a Chrome instance with a manually authenticated session (see start_browser.py).
Requests are issued from within the shop page via page.evaluate, i.e. with the page's own
origin and cookies, mirroring the requests of the shop frontend. The endpoints are
undocumented and may change; tools/watch_network.py records the frontend's requests for
re-analysis.
"""

import json
import time
from dataclasses import dataclass
from urllib.parse import quote

from playwright.sync_api import Page, Playwright, Response

CDP_URL = "http://127.0.0.1:9222"
SHOP_URL = "https://www.rewe.de/shop/"
BASKET_URL = "https://www.rewe.de/shop/checkout/basket"
SEARCH_PAGE_URL = "https://www.rewe.de/shop/productList?term="
BASKET_CHANGE_PATH = "/shop/api/baskets/listings/"  # endpoint for setting cart quantities
BASKET_MARKER = "const data = {"  # start of the basket JSON embedded in the cart page
MIN_SECONDS_BETWEEN_REQUESTS = 1.5  # rate limit towards the shop

SEARCH_JS = """
async (query) => {
  const r = await fetch('/shop/api/products?' + new URLSearchParams(query), {
    credentials: 'include',
    headers: {accept: 'application/vnd.rewe.digital.products+json;client=web;version=2'},
  });
  return {status: r.status, body: await r.text()};
}
"""

SET_QUANTITY_JS = """
async ([listingId, quantity]) => {
  const r = await fetch('/shop/api/baskets/listings/' + encodeURIComponent(listingId), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'accept': 'application/vnd.com.rewe.digital.basket-v2+json',
      'content-type': 'application/json',
      'x-application-id': 'rewe-basket',
      'x-origin': 'AddToBasketV2',
    },
    body: JSON.stringify({quantity, includeTimeslot: false, context: 'product-list-search'}),
  });
  return {status: r.status, body: await r.text()};
}
"""


class ReweError(Exception):
    """Error while communicating with the REWE shop."""


class NotLoggedIn(ReweError):
    """No valid shop session; manual login required."""


@dataclass
class Product:
    product_id: str
    listing_id: str
    title: str
    price_cents: int | None
    grammage: str  # e.g. "500g (1 kg = 2,50 €)"

    @property
    def price_text(self) -> str:
        if self.price_cents is None:
            return "?"
        return f"{self.price_cents / 100:.2f} €".replace(".", ",")


class ReweShop:
    def __init__(self, page: Page):
        self.page = page
        self.market_id: str | None = None
        self.service_type: str | None = None
        self.cart: dict[str, int] = {}  # productId -> quantity currently in the cart
        self._last_request = 0.0
        # Responses to cart changes are collected here and evaluated in take_user_adds().
        self._basket_responses: list[Response] = []
        page.on("response", self._on_response)

    # ---------- connection ----------

    @classmethod
    def connect(cls, playwright: Playwright) -> "ReweShop":
        """Attach to the running, manually authenticated Shopatron browser."""
        try:
            browser = playwright.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:
            raise ReweError(
                "Shopatron browser not reachable. Start it with:  "
                ".venv\\Scripts\\python.exe start_browser.py"
            ) from exc
        context = browser.contexts[0]
        page = next((pg for pg in context.pages if "rewe.de" in pg.url), None)
        if page is None:
            page = context.new_page()
            page.goto(SHOP_URL)
        page.bring_to_front()
        shop = cls(page)
        shop.read_cart()  # also determines market and service type
        return shop

    # ---------- reading ----------

    def read_cart(self) -> dict[str, int]:
        """Load the cart page and parse the basket JSON embedded in it."""
        self._pause()
        self.page.goto(BASKET_URL, wait_until="domcontentloaded")
        html = self.page.content()
        if BASKET_MARKER not in html:
            raise NotLoggedIn(
                "No basket data on the cart page; the session is probably not logged in. "
                "Log in manually in the Shopatron browser and retry."
            )
        start = html.index(BASKET_MARKER) + len(BASKET_MARKER) - 1
        basket, _ = json.JSONDecoder().raw_decode(html, start)
        self._update_from_basket(basket)
        return self.cart

    def search(self, term: str, limit: int = 10) -> list[Product]:
        query = {
            "term": term,
            "objectsPerPage": str(limit),
            "marketId": self.market_id,
            "serviceType": self.service_type,
        }
        self._pause()
        result = self.page.evaluate(SEARCH_JS, query)
        if result["status"] != 200:
            raise ReweError(f"Search failed with status {result['status']}: {result['body'][:200]}")
        hits = json.loads(result["body"]).get("hits", [])
        return [_product_from_hit(h) for h in hits if h.get("listingId")]

    def lookup(self, product_id: str) -> Product | None:
        """Find a product by its productId. None: not available in the current market."""
        return next((p for p in self.search(product_id) if p.product_id == product_id), None)

    # ---------- cart changes ----------

    def add(self, product: Product, quantity: int) -> int:
        """Add `quantity` units to the quantity already in the cart. Returns the new total."""
        return self.set_quantity(product, self.cart.get(product.product_id, 0) + quantity)

    def set_quantity(self, product: Product, total: int) -> int:
        """Set the absolute quantity of a product in the cart (equivalent to the shop's +/- buttons)."""
        self._pause()
        result = self.page.evaluate(SET_QUANTITY_JS, [product.listing_id, total])
        if result["status"] in (401, 403):
            raise NotLoggedIn("Cart change rejected by the shop; manual login required.")
        if result["status"] != 200:
            raise ReweError(f"Cart change failed with status {result['status']}: {result['body'][:200]}")
        # The response contains the complete updated basket.
        self._update_from_basket(json.loads(result["body"]))
        actual = self.cart.get(product.product_id, 0)
        if actual != total:
            raise ReweError(f"Expected {total} x {product.title} in the cart, shop reports {actual}.")
        return actual

    # ---------- manual selection on the shop page ----------

    def open_search_page(self, term: str) -> None:
        """Navigate the tab to the shop's regular search results page for `term`."""
        self._pause()
        self.page.goto(SEARCH_PAGE_URL + quote(term), wait_until="domcontentloaded")

    def take_user_adds(self) -> list[Product]:
        """Return products whose cart quantity increased since the previous call.

        Cart changes issued by set_quantity() are observed as well, but are already reflected
        in self.cart and therefore do not register as an increase.
        """
        increased = []
        responses, self._basket_responses = self._basket_responses, []
        for response in responses:
            try:
                if response.status != 200:
                    continue
                basket = response.json()
            except Exception:
                continue  # body no longer available (e.g. after navigation)
            before = dict(self.cart)
            self._update_from_basket(basket)
            for line in basket.get("lineItems", []):
                product = _product_from_line_item(line)
                if self.cart.get(product.product_id, 0) > before.get(product.product_id, 0):
                    increased.append(product)
        return increased

    def wait(self, ms: int) -> None:
        """Wait while allowing Playwright to dispatch browser events."""
        self.page.wait_for_timeout(ms)

    # ---------- internals ----------

    def _on_response(self, response: Response) -> None:
        if response.request.method == "POST" and BASKET_CHANGE_PATH in response.url:
            self._basket_responses.append(response)

    def _update_from_basket(self, basket: dict) -> None:
        selection = basket.get("serviceSelection", {})
        self.market_id = selection.get("wwIdent", self.market_id)
        self.service_type = selection.get("serviceType", self.service_type)
        self.cart = {}
        for item in basket.get("lineItems", []):
            pid = item["product"]["productId"]
            self.cart[pid] = self.cart.get(pid, 0) + item["quantity"]

    def _pause(self) -> None:
        """Enforce MIN_SECONDS_BETWEEN_REQUESTS between consecutive requests."""
        wait = self._last_request + MIN_SECONDS_BETWEEN_REQUESTS - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()


def _product_from_hit(hit: dict) -> Product:
    pricing = hit.get("pricing", {})
    return Product(
        product_id=str(hit["productId"]),
        listing_id=hit["listingId"],
        title=hit.get("title", "?"),
        price_cents=pricing.get("currentRetailPrice"),
        grammage=pricing.get("grammage", ""),
    )


def _product_from_line_item(line: dict) -> Product:
    """Product built from a basket line item (structure differs from search hits)."""
    product = line["product"]
    listing = product.get("listing", {})
    return Product(
        product_id=str(product["productId"]),
        listing_id=listing.get("listingId", ""),
        title=product.get("title", "?"),
        price_cents=line.get("price"),
        grammage=listing.get("grammage", ""),
    )
