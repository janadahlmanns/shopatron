"""ItemDB tests against a temporary database file. Product IDs are fictitious."""

from shopatron.db import ItemDB


def test_unknown_item_is_none(tmp_path):
    db = ItemDB(tmp_path / "test.db")
    assert db.get("Zwiebeln") is None


def test_default_lookup_ignores_case_and_whitespace(tmp_path):
    db = ItemDB(tmp_path / "test.db")
    db.set_default("Zwiebeln", "1000001", "Testprodukt A")
    item = db.get("  zwiebeln ")
    assert item.product_id == "1000001"
    assert item.name == "Zwiebeln"


def test_storing_again_replaces_the_default(tmp_path):
    db = ItemDB(tmp_path / "test.db")
    db.set_default("Zwiebeln", "1000001", "Testprodukt A")
    db.set_default("zwiebeln", "1000002", "Testprodukt B")
    assert db.get("Zwiebeln").product_id == "1000002"
    assert len(db.all()) == 1
