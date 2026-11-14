"""Persistence of item defaults: mapping of item names to default REWE products.

Backed by a single SQLite file (shopatron.db, excluded from version control) via the
standard-library sqlite3 module; no database server is required.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "shopatron.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    key           TEXT PRIMARY KEY,   -- normalized item name, used for lookups
    name          TEXT NOT NULL,      -- item name as first entered
    product_id    TEXT,               -- REWE productId of the default product, or NULL
    product_title TEXT,               -- product title, for display only
    updated_at    TEXT NOT NULL
);
"""


def normalize(name: str) -> str:
    """Lookup key: case-insensitive, with surrounding and repeated whitespace removed."""
    return " ".join(name.casefold().split())


@dataclass
class Item:
    key: str
    name: str
    product_id: str | None
    product_title: str | None


class ItemDB:
    def __init__(self, path: Path = DEFAULT_DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row  # rows support access by column name
        self.conn.executescript(SCHEMA)

    def get(self, name: str) -> Item | None:
        # "?" placeholders let sqlite3 insert values safely. SQL is never assembled by
        # string concatenation, which prevents SQL injection.
        row = self.conn.execute("SELECT * FROM items WHERE key = ?", (normalize(name),)).fetchone()
        return Item(row["key"], row["name"], row["product_id"], row["product_title"]) if row else None

    def set_default(self, name: str, product_id: str, product_title: str) -> None:
        # Upsert: insert a new row or, if the key already exists, update the existing row.
        self.conn.execute(
            """
            INSERT INTO items (key, name, product_id, product_title, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                product_id = excluded.product_id,
                product_title = excluded.product_title,
                updated_at = excluded.updated_at
            """,
            (normalize(name), name.strip(), product_id, product_title, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()  # persists the change to the database file

    def all(self) -> list[Item]:
        rows = self.conn.execute("SELECT * FROM items ORDER BY key").fetchall()
        return [Item(r["key"], r["name"], r["product_id"], r["product_title"]) for r in rows]

    def close(self) -> None:
        self.conn.close()
