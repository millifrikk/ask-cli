"""Tests for atomic, private JSON state-file storage."""

import json

import pytest

from ask_cli.core.storage import read_json_object, write_private_json
from ask_cli.exceptions import StorageError


class TestReadJsonObject:
    def test_missing_file_returns_none(self, tmp_path):
        assert read_json_object(tmp_path / "absent.json") is None

    def test_reads_object(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text('{"a": 1}')
        assert read_json_object(path) == {"a": 1}

    @pytest.mark.parametrize(
        "content",
        [b'{"truncated": ', b"\xff\xfe not utf-8", b"[1, 2]", b'"just a string"'],
        ids=["truncated", "invalid-utf8", "list", "string"],
    )
    def test_corrupt_content_raises_storage_error(self, tmp_path, content):
        path = tmp_path / "state.json"
        path.write_bytes(content)
        with pytest.raises(StorageError, match="state.json"):
            read_json_object(path)

    def test_unreadable_path_raises_storage_error(self, tmp_path):
        (tmp_path / "state.json").mkdir()
        with pytest.raises(StorageError):
            read_json_object(tmp_path / "state.json")


class TestWritePrivateJson:
    def test_round_trip_with_private_permissions(self, tmp_path):
        path = tmp_path / "nested" / "state.json"
        write_private_json(path, {"b": [1, 2]})
        assert json.loads(path.read_text()) == {"b": [1, 2]}
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700

    def test_tightens_previously_loose_file(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("{}")
        path.chmod(0o644)
        write_private_json(path, {"c": 3})
        assert path.stat().st_mode & 0o777 == 0o600

    def test_leaves_no_temp_files(self, tmp_path):
        directory = tmp_path / "state"
        write_private_json(directory / "state.json", {"d": 4})
        assert [p.name for p in directory.iterdir()] == ["state.json"]

    def test_failed_write_keeps_original_and_raises(self, tmp_path):
        directory = tmp_path / "state"
        directory.mkdir()
        path = directory / "state.json"
        path.write_text('{"original": true}')
        with pytest.raises(StorageError):
            write_private_json(path, {"bad": object()})
        assert json.loads(path.read_text()) == {"original": True}
        assert [p.name for p in directory.iterdir()] == ["state.json"]

    def test_unwritable_location_raises_storage_error(self, tmp_path):
        blocker = tmp_path / "file"
        blocker.write_text("")
        with pytest.raises(StorageError):
            write_private_json(blocker / "state.json", {})
