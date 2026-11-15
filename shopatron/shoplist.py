"""Parsing of a plain-text shopping list into entries (name, quantity, amount, choose flag).

Format: one item per line. An integer before or after the name specifies the quantity,
i.e. the number of units of the REWE product to place in the cart. Default quantity: 1.

    Zwiebeln            -> Entry("Zwiebeln", 1)
    3 Zwiebeln          -> Entry("Zwiebeln", 3)
    3x Zwiebeln         -> Entry("Zwiebeln", 3)
    Zwiebeln 3          -> Entry("Zwiebeln", 3)
    Zwiebeln x3         -> Entry("Zwiebeln", 3)
    # comment           -> ignored, as are empty lines

Amounts with a unit (e.g. "80g", "500 ml", "1,5 kg", "2 Liter", "6 Stück") are separated
from the name. They are not part of the search term or the item key and serve as a hint
during manual product selection:

    Parmesan 80g        -> Entry("Parmesan", 1, amount="80g")
    2 Sahne 200 ml      -> Entry("Sahne", 2, amount="200 ml")

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

# Number (optionally with decimal comma/point), optional space, unit. The lookarounds
# require whitespace or line boundaries on both sides, so units inside words do not match.
UNITS = r"mg|g|gr|gramm|kg|ml|cl|dl|l|ltr|liter|stk|st|stück"
AMOUNT = re.compile(rf"(?<!\S)\d+(?:[.,]\d+)?\s?(?:{UNITS})\.?(?!\S)", re.IGNORECASE)


@dataclass
class Entry:
    name: str
    quantity: int = 1
    choose: bool = False  # True: bypass the stored default, select the product manually
    amount: str = ""  # amount with unit from the list line, e.g. "80g"; display only


def _strip_choose_marker(line: str) -> tuple[str, bool]:
    """Remove a leading/trailing '?' or a trailing ' -'. Returns (remaining text, marker present)."""
    if line.startswith("?"):
        return line[1:].strip(), True
    if line.endswith("?"):
        return line[:-1].strip(), True
    if line.endswith(" -") or line == "-":
        return line[:-1].strip(), True
    return line, False


def _extract_amounts(line: str) -> tuple[str, str]:
    """Remove amounts with units. Returns (remaining text, removed amounts joined by spaces)."""
    amounts = [m.group(0) for m in AMOUNT.finditer(line)]
    rest = " ".join(AMOUNT.sub(" ", line).split())
    return rest, " ".join(amounts)


def parse_line(line: str) -> Entry | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    # Marker and amounts are removed before the quantity is parsed, so the quantity rules
    # apply to the remaining "<quantity> <name>" text unchanged.
    line, choose = _strip_choose_marker(line)
    line, amount = _extract_amounts(line)
    if not line:
        return None
    if m := QTY_FIRST.match(line):
        return Entry(m.group(2).strip(), int(m.group(1)), choose, amount)
    if m := QTY_LAST.match(line):
        return Entry(m.group(1).strip(), int(m.group(2)), choose, amount)
    return Entry(line, 1, choose, amount)


def parse_list(text: str) -> list[Entry]:
    entries = (parse_line(line) for line in text.splitlines())
    return [e for e in entries if e is not None and e.quantity > 0]
