"""Shopping list parser tests."""

from shopatron.shoplist import Entry, parse_line, parse_list


def test_plain_name_means_one():
    assert parse_line("Zwiebeln") == Entry("Zwiebeln", 1)


def test_quantity_first():
    assert parse_line("3 Zwiebeln") == Entry("Zwiebeln", 3)
    assert parse_line("3x Zwiebeln") == Entry("Zwiebeln", 3)
    assert parse_line("3 x Zwiebeln") == Entry("Zwiebeln", 3)


def test_quantity_last():
    assert parse_line("Zwiebeln 3") == Entry("Zwiebeln", 3)
    assert parse_line("Zwiebeln x3") == Entry("Zwiebeln", 3)
    assert parse_line("Zwiebeln 3x") == Entry("Zwiebeln", 3)


def test_numbers_inside_names_are_not_quantities():
    assert parse_line("Müllbeutel 60l") == Entry("Müllbeutel 60l", 1)
    assert parse_line("2 Müllbeutel 60l") == Entry("Müllbeutel 60l", 2)


def test_comments_and_empty_lines_are_ignored():
    text = "# Wocheneinkauf\n\n  Milch  \n2 Butter\n"
    assert parse_list(text) == [Entry("Milch", 1), Entry("Butter", 2)]


def test_zero_quantity_is_dropped():
    assert parse_list("0 Zwiebeln") == []


def test_no_marker_means_use_default():
    assert parse_line("Milch 5").choose is False


def test_choose_marker_in_all_positions():
    for line in ["Milch 5 ?", "Milch 5?", "5 Milch ?", "? 5 Milch", "?5 Milch", "Milch 5 -"]:
        assert parse_line(line) == Entry("Milch", 5, choose=True), line
    for line in ["Milch ?", "? Milch", "Milch?", "Milch -"]:
        assert parse_line(line) == Entry("Milch", 1, choose=True), line


def test_dash_inside_names_is_not_a_marker():
    assert parse_line("Coca-Cola 2") == Entry("Coca-Cola", 2)
    assert parse_line("Frischkäse - Kräuter") == Entry("Frischkäse - Kräuter", 1)


def test_line_with_only_a_marker_is_ignored():
    assert parse_list("?\n-") == []
