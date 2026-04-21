"""Tests for YAML serialization."""

import yaml

from telegram_mcp_server.yaml_utils import to_yaml


def _roundtrip(value):
    return yaml.safe_load(to_yaml(value))


def test_simple_string():
    result = _roundtrip({"key": "hello"})
    assert result == {"key": "hello"}


def test_multiline_string_uses_block_style():
    text = "line one\nline two"
    dumped = to_yaml({"key": text})
    # literal block style: | or |- (no trailing newline)
    assert ("|\n" in dumped or "|-\n" in dumped)
    assert _roundtrip({"key": text}) == {"key": text}


def test_plain_string_no_pipe():
    dumped = to_yaml({"key": "simple"})
    assert "|\n" not in dumped


def test_unicode_preserved():
    result = _roundtrip({"emoji": "😊"})
    assert result == {"emoji": "😊"}


def test_list_of_dicts():
    value = [{"a": 1}, {"b": "two\nlines"}]
    result = _roundtrip(value)
    assert result == value


def test_none_values():
    result = _roundtrip({"x": None})
    assert result == {"x": None}


def test_boolean_values():
    result = _roundtrip({"flag": True})
    assert result["flag"] is True


def test_special_yaml_chars_in_string():
    # Strings containing : and # should still round-trip correctly
    text = "key: value # comment"
    result = _roundtrip({"msg": text})
    assert result == {"msg": text}
