"""Read-only comparisons of pinned legal sources."""
import json
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def _source_inventory():
    return json.loads(files("aiact").joinpath("data/official/sources.json").read_text())


def source_info(snapshot):
    document = next((doc for doc in snapshot.documents
                     if doc.metadata.celex == snapshot.source_version), None)
    entry = next((item for item in _source_inventory()
                  if item["celex"] == snapshot.source_version
                  and item["sha256"] in snapshot.source_hashes), None)
    return {
        "snapshot_id": snapshot.snapshot_id,
        "version": snapshot.source_version,
        "url": entry["canonical_url"] if entry else (document.source_url if document else None),
        "retrieved_at": entry["retrieved_at"] if entry else None,
        "consolidated_date": document.metadata.consolidated_date if document else None,
        "publication_date": document.metadata.publication_date if document else None,
    }


def _legal_metadata(document):
    return document.metadata.model_dump(exclude={"celex", "consolidated_date", "publication_date"})


def source_changes(previous, current):
    before = {doc.id: doc for doc in previous.documents}
    after = {doc.id: doc for doc in current.documents}
    changes = []
    for identity in sorted(before.keys() | after.keys()):
        old, new = before.get(identity), after.get(identity)
        if old is None or new is None:
            kind = "added" if new else "removed"
        elif (old.checksum, _legal_metadata(old), old.kind) != (new.checksum, _legal_metadata(new), new.kind):
            kind = "changed"
        else:
            continue
        changes.append({"id": identity, "title": (new or old).title, "change": kind})
    return changes


def affected_findings(previous, current, rows):
    changes = source_changes(previous, current)
    changed_docs = {change["id"] for change in changes}
    old_docs = {doc.id: doc for doc in previous.documents}
    new_docs = {doc.id: doc for doc in current.documents}
    scope_changes = {identity for identity in old_docs.keys() & new_docs.keys()
                     if _legal_metadata(old_docs[identity]) != _legal_metadata(new_docs[identity])
                     or old_docs[identity].kind != new_docs[identity].kind}
    old_chunks = {chunk.id: chunk for chunk in previous.chunks}
    new_chunks = {chunk.id: chunk for chunk in current.chunks}
    impacted = []
    for row in rows:
        payload = row["payload"]
        if payload.get("source_snapshot_id") != previous.snapshot_id:
            continue
        affected = set()
        for citation in payload.get("citations") or []:
            identity = citation.get("section_id")
            chunk = old_chunks.get(identity)
            replacement = new_chunks.get(identity)
            if chunk and (replacement is None or replacement.checksum != chunk.checksum
                          or chunk.document_id in scope_changes):
                affected.add(chunk.document_id)
            elif identity in changed_docs:
                affected.add(identity)
        if affected:
            impacted.append({
                "id": row["id"], "repository": row["name"], "title": payload.get("title") or "Finding",
                "review_id": payload.get("source_review_id"), "provisions": sorted(affected),
            })
    return impacted
