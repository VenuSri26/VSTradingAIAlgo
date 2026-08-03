from pathlib import Path

from app import version


def test_release_version_file_is_source_of_truth(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "stale-version")
    expected = (Path(version.__file__).resolve().parents[2] / "VERSION").read_text().strip()
    assert version._read_version() == expected
