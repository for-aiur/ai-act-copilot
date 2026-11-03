import pytest
pytest.importorskip("sqlalchemy")
from aiact.rag.domains import load_snapshot
from aiact.rag.store import Store


def test_snapshot_immutable_and_restart(tmp_path):
    url = "sqlite:///" + str(tmp_path / "db.sqlite")
    store = Store(url)
    snapshot = load_snapshot()
    doc = next(d for d in snapshot.documents if d.id == "article-6")
    assert doc.metadata.applicability_date is None
    assert {r.date for r in doc.metadata.applicability_rules} == {"2027-12-02", "2028-08-02"}
    store.put_snapshot(snapshot)
    store.put_snapshot(snapshot)
    store.append("review", "test", snapshot.domain_id, {"snapshot_id": snapshot.snapshot_id, "sources": ["article-113"]})
    store.close()
    store = Store(url)
    assert store.snapshot(snapshot.snapshot_id) == snapshot
    assert store.record("review", "test", 1)["snapshot_id"] == snapshot.snapshot_id
    with pytest.raises(ValueError, match="collision"):
        store.put_snapshot(snapshot.model_copy(update={"source_version": "changed"}))
    assert store.list_records("review", "workbench-api") == []
    store.close()


def test_activation_and_rollback_are_explicit_and_domain_scoped(tmp_path):
    store = Store("sqlite:///" + str(tmp_path / "db.sqlite"))
    for identity in ("old", "new"):
        store.put_release({"rag_release_id": identity, "domain_id": "one", "snapshot_id": "source"})
    store.activate("one", "old")
    store.activate("one", "new")
    assert store.pointer("one", "previous") == "old"
    store.activate("one", store.pointer("one", "previous"))
    assert store.pointer("one") == "old"
    with pytest.raises(ValueError, match="different domain"):
        store.activate("two", "new")
    store.close()
