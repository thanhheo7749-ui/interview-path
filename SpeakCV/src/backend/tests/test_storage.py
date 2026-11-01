import pytest

from app.core import storage


@pytest.fixture(autouse=True)
def _root(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))


def test_round_trip_uses_a_generated_name():
    path = storage.save_bytes(7, "documents", ".pdf", b"data")
    assert storage.read_bytes(path) == b"data"
    assert path.startswith("7/documents/") and path.endswith(".pdf")


def test_read_refuses_to_escape_the_root():
    with pytest.raises(ValueError):
        storage.read_bytes("../../etc/passwd")


def test_delete_is_idempotent():
    path = storage.save_bytes(7, "documents", ".txt", b"x")
    storage.delete(path)
    storage.delete(path)
