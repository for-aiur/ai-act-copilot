"""Append-only context-scoped annotation history. No ranking mutation."""
from uuid import uuid4
from .contracts import GoldenCase, RetrievalResult


def save_case(store, case: GoldenCase):
    snapshot = store.snapshot(case.snapshot_id)
    if case.request.domain_id != snapshot.domain_id:
        raise ValueError("Case domain does not match source snapshot")
    if not {label.document_id for label in case.labels} <= {d.id for d in snapshot.documents}:
        raise ValueError("Labels must reference documents in the pinned source snapshot")
    manifest = store.release(case.rag_release_id)
    if manifest["snapshot_id"] != case.snapshot_id:
        raise ValueError("Case release/source versions differ")
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
