"""ReweShop.take_user_adds(): detection of manually added products, using stub responses.

All IDs are fictitious.
"""

from shopatron.rewe import ReweShop


class StubPage:
    def on(self, event, handler):
        pass


class StubRequest:
    method = "POST"


class StubResponse:
    request = StubRequest()
    url = "https://www.rewe.de/shop/api/baskets/listings/0-0000000-test"
    status = 200

    def __init__(self, basket):
        self._basket = basket

    def json(self):
        return self._basket


def basket(*lines):
    return {
        "serviceSelection": {"wwIdent": "000000", "serviceType": "PICKUP"},
        "lineItems": [
            {"quantity": q, "price": 100,
             "product": {"productId": pid, "title": f"Testprodukt {pid}", "listing": {"listingId": f"L-{pid}"}}}
            for pid, q in lines
        ],
    }


def make_shop(cart):
    shop = ReweShop(StubPage())
    shop.cart = dict(cart)
    return shop


def test_newly_added_product_is_detected():
    shop = make_shop({"1000002": 2})
    shop._on_response(StubResponse(basket(("1000002", 2), ("1000001", 1))))
    added = shop.take_user_adds()
    assert [p.product_id for p in added] == ["1000001"]
    assert added[0].listing_id == "L-1000001"
    assert shop.cart == {"1000002": 2, "1000001": 1}


def test_own_cart_change_is_not_reported_as_user_add():
    # set_quantity() has already updated shop.cart; the corresponding response shows no increase.
    shop = make_shop({"1000001": 3})
    shop._on_response(StubResponse(basket(("1000001", 3))))
    assert shop.take_user_adds() == []


def test_decrease_is_not_reported():
    shop = make_shop({"1000001": 2})
    shop._on_response(StubResponse(basket(("1000001", 1))))
    assert shop.take_user_adds() == []
    assert shop.cart == {"1000001": 1}


def test_each_response_is_processed_once():
    shop = make_shop({})
    shop._on_response(StubResponse(basket(("1000001", 1))))
    assert len(shop.take_user_adds()) == 1
    assert shop.take_user_adds() == []
