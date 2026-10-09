"""Tests for usage statistics tracking."""

from ask_cli.core.stats import load_stats, record_query, reset_stats


def test_load_missing_returns_empty(tmp_path):
    stats = load_stats(tmp_path / "stats.json")
    assert stats["total_queries"] == 0
    assert stats["input_chars"] == 0
    assert stats["output_chars"] == 0


def test_record_creates_file(tmp_path):
    path = tmp_path / "stats.json"
    assert not path.exists()
    record_query(path, "default", 10, 20)
    assert path.exists()


def test_record_writes_mode_0600(tmp_path):
    path = tmp_path / "stats.json"
    record_query(path, "default", 10, 20)
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600


def test_record_increments_total_queries(tmp_path):
    path = tmp_path / "stats.json"
    record_query(path, "default", 10, 20)
    stats = load_stats(path)
    assert stats["total_queries"] == 1


def test_record_accumulates_chars(tmp_path):
    path = tmp_path / "stats.json"
    record_query(path, "default", 10, 20)
    record_query(path, "default", 5, 15)
    stats = load_stats(path)
    assert stats["input_chars"] == 15
    assert stats["output_chars"] == 35


def test_record_tracks_mode(tmp_path):
    path = tmp_path / "stats.json"
    record_query(path, "docker", 10, 20)
    stats = load_stats(path)
    assert stats["queries_by_mode"]["docker"] == 1


def test_record_sets_first_and_last_use(tmp_path):
    path = tmp_path / "stats.json"
    record_query(path, "default", 5, 10)
    stats1 = load_stats(path)
    first = stats1["first_use"]
    assert first is not None

    record_query(path, "default", 5, 10)
    stats2 = load_stats(path)
    # first_use must not change on subsequent calls
    assert stats2["first_use"] == first
    # last_use is always updated
    assert stats2["last_use"] is not None


def test_reset_writes_empty(tmp_path):
    path = tmp_path / "stats.json"
    record_query(path, "default", 100, 200)
    reset_stats(path)
    stats = load_stats(path)
    assert stats["total_queries"] == 0
    assert stats["input_chars"] == 0
    assert stats["queries_by_mode"] == {}


def test_corrupt_stats_raise_storage_error_with_reset_hint(tmp_path):
    import pytest

    from ask_cli.exceptions import StorageError

    path = tmp_path / "stats.json"
    path.write_text("[]")
    with pytest.raises(StorageError) as exc_info:
        load_stats(path)
    assert "ask --stats-reset" in exc_info.value.hint
    with pytest.raises(StorageError):
        record_query(path, "default", 1, 1)


def test_reset_failure_is_reported(tmp_path):
    import pytest

    from ask_cli.exceptions import StorageError

    blocker = tmp_path / "file"
    blocker.write_text("")
    with pytest.raises(StorageError):
        reset_stats(blocker / "stats.json")


def test_reset_repairs_corrupt_file(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text("{broken")
    reset_stats(path)
    assert load_stats(path)["total_queries"] == 0
