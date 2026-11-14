"""Parsing of a plain-text shopping list into entries (name, quantity, choose flag).

Format: one item per line. An integer before or after the name specifies the quantity,
i.e. the number of units of the REWE product to place in the cart. Default quantity: 1.

    Zwiebeln            -> Entry("Zwiebeln", 1)
    3 Zwiebeln          -> Entry("Zwiebeln", 3)
    3x Zwiebeln         -> Entry("Zwiebeln", 3)
    Zwiebeln 3          -> Entry("Zwiebeln", 3)
    Zwiebeln x3         -> Entry("Zwiebeln", 3)
    Müllbeutel 60l      -> Entry("Müllbeutel 60l", 1)   ("60l" is not a plain integer)
    # comment           -> ignored, as are empty lines

Choose marker: a "?" at the start or end of a line, or a trailing " -", bypasses the
stored default product for that entry and triggers manual product selection:

    Milch 5 ?    ? Milch    Milch 5?    Milch 5 -
"""

import re
from dataclasses import dataclass

# ^ / $ anchor the pattern to the start / end of the line; (\d+) captures the quantity;
# x? matches an optional multiplication sign; (.+) / (.+?) capture the item name.
QTY_FIRST = re.compile(r"^(\d+)\s*x?\s+(.+)$", re.IGNORECASE)
QTY_LAST = re.compile(r"^(.+?)\s+x?(\d+)x?$", re.IGNORECASE)


@dataclass
class Entry:
    name: str
    quantity: int = 1
    choose: bool = False  # True: bypass the stored default, select the product manually


def _strip_choose_marker(line: str) -> tuple[str, bool]:
    """Remove a leading/trailing '?' or a trailing ' -'. Returns (remaining text, marker present)."""
    if line.startswith("?"):
        return line[1:].strip(), True
    if line.endswith("?"):
        return line[:-1].strip(), True
    if line.endswith(" -") or line == "-":
        return line[:-1].strip(), True
    return line, False


def parse_line(line: str) -> Entry | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    # The marker is removed before the quantity is parsed, so the quantity rules apply unchanged.
    line, choose = _strip_choose_marker(line)
    if not line:
        return None
    if m := QTY_FIRST.match(line):
        return Entry(m.group(2).strip(), int(m.group(1)), choose)
    if m := QTY_LAST.match(line):
        return Entry(m.group(1).strip(), int(m.group(2)), choose)
    return Entry(line, 1, choose)


def parse_list(text: str) -> list[Entry]:
    entries = (parse_line(line) for line in text.splitlines())
    return [e for e in entries if e is not None and e.quantity > 0]
