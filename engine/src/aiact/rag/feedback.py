"""Append-only context-scoped annotation history. No ranking mutation."""
from uuid import uuid4
from .contracts import GoldenCase, RetrievalResult


def save_case(store, case: GoldenCase):
    snapshot = store.snapshot(case.snapshot_id)
    if case.request.domain_id != snapshot.domain_id:
        raise ValueError("Case domain does not match source snapshot")
    if not {label.document_id for label in case.labels} <= {d.id for d in snapshot.documents}:
        raise ValueError("Labels must reference documents in the pinned source snapshot")
    chunks = {c.id: c for c in snapshot.chunks}
    if any(label.chunk_id and (label.chunk_id not in chunks or chunks[label.chunk_id].document_id != label.document_id) for label in case.labels):
        raise ValueError("Paragraph labels must reference a chunk of their pinned parent document")
    manifest = store.release(case.rag_release_id)
    if manifest["snapshot_id"] != case.snapshot_id:
        raise ValueError("Case release/source versions differ")
    if case.status == "approved":
        positive = {"must_retrieve", "relevant"}
        for previous in latest_cases(store, case.request.domain_id):
            if previous.id == case.id or previous.status != "approved" or previous.snapshot_id != case.snapshot_id or previous.request.fingerprint() != case.request.fingerprint():
                continue
            for old in previous.labels:
                for new in case.labels:
                    overlap = old.document_id == new.document_id and (old.chunk_id is None or new.chunk_id is None or old.chunk_id == new.chunk_id)
                    contradiction = (old.label in positive and new.label == "not_relevant") or (new.label in positive and old.label == "not_relevant")
                    if overlap and contradiction:
                        raise ValueError("Conflicting approved labels for this exact context. Reconcile the existing case before approving a contradictory case.")
    store.append("case", case.id, case.request.domain_id, case.model_dump(mode="json"), case.revision)
    return case


def save_run(store, result: RetrievalResult):
    identity = str(uuid4())
    store.append("retrieval", identity, result.request.domain_id, result.model_dump(mode="json"))
    return identity


def latest_cases(store, domain):
    latest = {}
    for row in store.list_records("case", domain, limit=1000):
        case = GoldenCase.model_validate(row["payload"])
        if case.id not in latest or case.revision > latest[case.id].revision:
            latest[case.id] = case
    return list(latest.values())
