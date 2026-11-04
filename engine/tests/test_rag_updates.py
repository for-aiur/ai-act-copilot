from aiact.rag.domains import load_snapshot
from aiact.rag.updates import diff_snapshots


def test_diff_reports_changed_chunks_and_affected_reviews_without_mutating_old():
    before = load_snapshot("workbench-api")
    chunk = before.chunks[0]
    changed = chunk.model_copy(update={"title": "Changed source heading"})
    after = before.model_copy(update={"snapshot_id": "new", "chunks": (changed, *before.chunks[1:])})
    report = diff_snapshots(before, after, [{"id": "old-review", "payload": {"scan_result": {"findings": [{"citations": [{"section_id": chunk.id}]}]}}}])
    assert report["chunks"]["modified"] == [chunk.id]
    assert report["affected_reviews"][0]["review_id"] == "old-review"
    assert before.chunks[0].title != changed.title
