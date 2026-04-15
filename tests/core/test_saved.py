"""Tests for saved response persistence — save, recall, list, delete."""

import time
from pathlib import Path

import pytest

from ask_cli.core.saved import delete_saved, list_saved, recall_response, save_response
from ask_cli.exceptions import SavedResponseError


@pytest.fixture
def saved_dir(tmp_path) -> Path:
    return tmp_path / "saved"


def test_save_and_recall_roundtrip(saved_dir):
    save_response("myanswer", "my query", "my response", saved_dir)
    entry = recall_response("myanswer", saved_dir)
    assert entry["query"] == "my query"
    assert entry["response"] == "my response"
    assert entry["name"] == "myanswer"
    assert "timestamp" in entry


def test_save_writes_mode_0600(saved_dir):
    save_response("myanswer", "my query", "my response", saved_dir)
    path = saved_dir / "myanswer.json"
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600


def test_recall_not_found_raises(saved_dir):
    with pytest.raises(SavedResponseError, match="No saved response"):
        recall_response("missing", saved_dir)


def test_list_empty_when_dir_absent(saved_dir):
    assert list_saved(saved_dir) == []


def test_list_sorted_by_timestamp(saved_dir):
    save_response("first", "q1", "r1", saved_dir)
    time.sleep(0.01)
    save_response("second", "q2", "r2", saved_dir)
    entries = list_saved(saved_dir)
    assert len(entries) == 2
    # Most recent (second) should appear first
    assert entries[0]["name"] == "second"
    assert entries[1]["name"] == "first"


def test_delete_removes_file(saved_dir):
    save_response("todelete", "q", "r", saved_dir)
    assert (saved_dir / "todelete.json").exists()
    delete_saved("todelete", saved_dir)
    assert not (saved_dir / "todelete.json").exists()


def test_delete_not_found_raises(saved_dir):
    with pytest.raises(SavedResponseError, match="No saved response"):
        delete_saved("ghost", saved_dir)


def test_invalid_name_slash_raises(saved_dir):
    with pytest.raises(SavedResponseError, match="invalid characters"):
        save_response("foo/bar", "q", "r", saved_dir)


def test_invalid_name_backslash_raises(saved_dir):
    with pytest.raises(SavedResponseError, match="invalid characters"):
        save_response("foo\\bar", "q", "r", saved_dir)


def test_invalid_name_leading_dot_raises(saved_dir):
    with pytest.raises(SavedResponseError, match="must not start"):
        save_response(".hidden", "q", "r", saved_dir)


def test_save_overwrites_existing(saved_dir):
    save_response("mykey", "old query", "old response", saved_dir)
    save_response("mykey", "new query", "new response", saved_dir)
    entry = recall_response("mykey", saved_dir)
    assert entry["query"] == "new query"
    assert entry["response"] == "new response"
