from mcp_eval_gate.text_diff import describe_difference, preview


def test_reports_the_first_differing_character_with_context():
    result = describe_difference("hello world", "hello there")

    assert "first difference at char 6" in result
    assert "expected 'hello world'" in result
    assert "got 'hello there'" in result


def test_reports_lengths_of_both_strings():
    result = describe_difference("abc", "abcdef")

    assert "expected 3 chars" in result
    assert "got 6" in result


def test_difference_at_end_of_a_long_string_stays_short_and_shows_context():
    expected = "a" * 1023 + "界"
    actual = "a" * 1023 + "���"

    result = describe_difference(expected, actual)

    assert len(result) < 250
    assert "first difference at char 1023" in result
    assert "界" in result
    assert "�" in result
    assert "…" in result


def test_difference_at_the_start_has_no_leading_ellipsis():
    result = describe_difference("界" + "a" * 500, "�" + "a" * 500)

    assert "first difference at char 0" in result
    assert "'…" not in result


def test_prefix_only_difference_is_reported_at_the_end_of_the_shorter_string():
    result = describe_difference("abc", "abcd")

    assert "first difference at char 3" in result


def test_preview_returns_short_text_unchanged():
    assert preview("short") == "short"


def test_preview_truncates_long_text_and_says_how_much_was_cut():
    result = preview("x" * 500, limit=50)

    assert result.startswith("x" * 50)
    assert "450 more chars" in result
    assert len(result) < 100
