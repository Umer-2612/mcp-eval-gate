import json

import pytest

from mcp_eval_gate.normalize import NormalizeError, apply_normalizers, parse_normalizers


def test_no_normalizers_leaves_text_untouched():
    assert apply_normalizers("  hello\n", ()) == "  hello\n"


def test_trim_strips_surrounding_whitespace_only():
    normalizers = parse_normalizers(["trim"])

    assert apply_normalizers("  a  b\n", normalizers) == "a  b"


def test_tmp_paths_replaces_temporary_directories():
    normalizers = parse_normalizers(["tmp_paths"])

    text = "wrote /tmp/tmpab12cd/out.txt and /var/folders/x9/k2m3/T/tmp99zz/log"
    result = apply_normalizers(text, normalizers)

    assert result == "wrote <tmp>/out.txt and <tmp>/log"


def test_regex_normalizer_replaces_every_match():
    normalizers = parse_normalizers([{"regex": r"\d{4}-\d{2}-\d{2}", "replace": "<date>"}])

    assert apply_normalizers("from 2026-01-02 to 2026-03-04", normalizers) == "from <date> to <date>"


def test_regex_normalizer_defaults_the_replacement_to_a_placeholder():
    normalizers = parse_normalizers([{"regex": r"id=\w+"}])

    assert apply_normalizers("id=abc123 ok", normalizers) == "<normalized> ok"


def test_ignore_keys_drops_the_named_keys_at_any_depth_of_json_text():
    normalizers = parse_normalizers([{"ignore_keys": ["id", "created_at"]}])
    text = json.dumps({"id": 1, "name": "x", "items": [{"id": 2, "created_at": "now", "v": 3}]})

    result = json.loads(apply_normalizers(text, normalizers))

    assert result == {"name": "x", "items": [{"v": 3}]}


def test_ignore_keys_leaves_non_json_text_alone():
    normalizers = parse_normalizers([{"ignore_keys": ["id"]}])

    assert apply_normalizers("id: 7", normalizers) == "id: 7"


def test_normalizers_apply_in_the_order_they_are_listed():
    normalizers = parse_normalizers([{"regex": "a+", "replace": "b"}, {"regex": "b+", "replace": "c"}])

    assert apply_normalizers("aaa", normalizers) == "c"


@pytest.mark.parametrize(
    "raw, message",
    [
        (["nope"], "unknown normalizer"),
        ([{"regex": "("}], "invalid regex"),
        ([{"unknown_key": 1}], "unknown normalizer"),
        ([{"ignore_keys": "id"}], "ignore_keys"),
        ("trim", "list"),
    ],
)
def test_invalid_normalizer_definitions_raise_a_readable_error(raw, message):
    with pytest.raises(NormalizeError, match=message):
        parse_normalizers(raw)
