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
