"""Block 4 group Y on a real MySQL: the migrated schema takes the masking note, and two retries of the masking rebuild a
document once. See test_mysql_brain_races for the method."""
import os
import threading

import pytest

if not os.environ.get("TEST_MYSQL_URL", "").strip():
    pytest.skip("Needs TEST_MYSQL_URL; run `make test-mysql`.", allow_module_level=True)

from fastapi.testclient import TestClient

from app.bridges import intake
from app.database.sql_models import KbDocument, KbIngestionJob, VoiceTurn
from app.main import app
from tests.helpers import auth_header
from tests.test_bridges_intake import (  # noqa: F401 - fixtures the helpers below rely on
    HR, _dirs, scheduled, unmasked_document, world,
)


def test_the_note_and_the_migrated_columns_survive_a_real_database(client, world, db, monkeypatch):
    session, document = unmasked_document(client, world, db, monkeypatch)
    assert document.masking_note == intake.MASK_FAILED
    db.rollback()  # a fresh snapshot: other sessions committed
    db.expire_all()
    assert db.query(VoiceTurn).filter(VoiceTurn.session_id == session.id, VoiceTurn.transcript.isnot(None)).count() > 0
    listed = client.get(f"/api/companies/{world.company.id}/kb/documents", headers=auth_header(HR)).json()
    assert [d["masking_note"] for d in listed if d["id"] == document.id] == [intake.MASK_FAILED]


def test_two_retries_of_the_masking_rebuild_the_document_once(client, world, db, monkeypatch):
    session, document = unmasked_document(client, world, db, monkeypatch)
    path = f"/api/companies/{world.company.id}/kb/documents/{document.id}/retry-masking"
    barrier = threading.Barrier(2)
    results = []

    def retry():
        with TestClient(app) as own:
            barrier.wait()
            results.append(own.post(path, headers=auth_header(HR)).status_code)

    threads = [threading.Thread(target=retry) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [200, 409]
    db.rollback()  # a fresh snapshot: other sessions committed
    db.expire_all()
    assert db.get(KbDocument, document.id).masking_note is None
    assert db.query(KbIngestionJob).filter_by(document_id=document.id).count() == 2
    assert all(t.transcript is None for t in db.query(VoiceTurn).filter_by(session_id=session.id))
