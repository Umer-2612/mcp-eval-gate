"""Normalizers make volatile tool output comparable: timestamps, temp paths, generated ids.

They are applied at compare time to both the recorded and the current output, so the baseline
keeps the raw text and a change of normalizer never needs a re-record.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

DEFAULT_REPLACEMENT = "<normalized>"
TMP_PATH_PATTERN = re.compile(r"(?:/private)?(?:/var/folders/[^/\s]+/[^/\s]+/T|/tmp)/[^/\s]+")
TMP_PLACEHOLDER = "<tmp>"


class NormalizeError(ValueError):
    """Raised when a normalizer definition in the golden set is invalid."""


@dataclass(frozen=True)
class Normalizer:
    kind: str
    pattern: re.Pattern[str] | None = None
    replacement: str = DEFAULT_REPLACEMENT
    keys: frozenset[str] = frozenset()


def parse_normalizers(raw: object) -> tuple[Normalizer, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise NormalizeError("`normalize` must be a list")
    return tuple(_parse_one(item) for item in raw)


def _parse_one(item: object) -> Normalizer:
    if item == "trim":
        return Normalizer("trim")
    if item == "tmp_paths":
        return Normalizer("regex", pattern=TMP_PATH_PATTERN, replacement=TMP_PLACEHOLDER)
    if isinstance(item, dict) and set(item) <= {"regex", "replace"} and "regex" in item:
        try:
            pattern = re.compile(item["regex"])
        except re.error as exc:
            raise NormalizeError(f"invalid regex {item['regex']!r}: {exc}") from exc
        return Normalizer("regex", pattern=pattern, replacement=item.get("replace", DEFAULT_REPLACEMENT))
    if isinstance(item, dict) and set(item) == {"ignore_keys"}:
        keys = item["ignore_keys"]
        if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
            raise NormalizeError("ignore_keys must be a list of key names")
        return Normalizer("ignore_keys", keys=frozenset(keys))
    raise NormalizeError(
        f"unknown normalizer {item!r}. Use trim, tmp_paths, {{regex, replace}}, or {{ignore_keys: [...]}}"
    )


def apply_normalizers(text: str, normalizers: tuple[Normalizer, ...]) -> str:
    for normalizer in normalizers:
        if normalizer.kind == "trim":
            text = text.strip()
        elif normalizer.kind == "regex" and normalizer.pattern is not None:
            text = normalizer.pattern.sub(normalizer.replacement, text)
        elif normalizer.kind == "ignore_keys":
            text = _drop_keys_from_json_text(text, normalizer.keys)
    return text


def normalize_structured(value: object, normalizers: tuple[Normalizer, ...]) -> object:
    for normalizer in normalizers:
        if normalizer.kind == "ignore_keys":
            value = _drop_keys(value, normalizer.keys)
    return value


def _drop_keys_from_json_text(text: str, keys: frozenset[str]) -> str:
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    return json.dumps(_drop_keys(parsed, keys), sort_keys=True)


def _drop_keys(value: object, keys: frozenset[str]) -> object:
    if isinstance(value, dict):
        return {k: _drop_keys(v, keys) for k, v in value.items() if k not in keys}
    if isinstance(value, list):
        return [_drop_keys(v, keys) for v in value]
    return value
