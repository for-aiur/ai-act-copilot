from types import SimpleNamespace

import pytest

pytest.importorskip("sqlalchemy")

from aiact.rag.contracts import SourceMetadata
from aiact.workbench.source_updates import affected_findings, source_changes


def test_changed_passage_flags_only_findings_pinned_to_its_old_snapshot():
    meta = SourceMetadata(origin="consolidated", celex="old")
    old_doc = SimpleNamespace(id="article-14", checksum="old", metadata=meta, kind="article", title="Human oversight")
    new_doc = SimpleNamespace(id="article-14", checksum="new", metadata=meta.model_copy(update={"celex": "new"}),
                              kind="article", title="Human oversight")

    def chunk(number, checksum):
        return SimpleNamespace(id=f"article-14-{number}", document_id="article-14", checksum=checksum)

    previous = SimpleNamespace(snapshot_id="old", documents=[old_doc], chunks=[chunk(1, "old"), chunk(2, "same")])
    current = SimpleNamespace(snapshot_id="new", documents=[new_doc], chunks=[chunk(1, "new"), chunk(2, "same")])
    assert source_changes(previous, current) == [{"id":"article-14", "title":"Human oversight", "change":"changed"}]
    rows = [
        {"id": key, "name": "test/repo", "payload": {"source_snapshot_id": snapshot,
         "citations": [{"section_id": citation}]}}
        for key, snapshot, citation in [
            ("changed", "old", "article-14-1"),
            ("unchanged", "old", "article-14-2"),
            ("different-version", "new", "article-14-1"),
        ]
    ]
    assert [item["id"] for item in affected_findings(previous, current, rows)] == ["changed"]
