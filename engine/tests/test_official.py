import gzip
import json
import shutil
from importlib.resources import files

import pytest

from aiact.rag.official import import_official, checksum


def test_full_official_inventory_and_rebuild():
    snapshot = import_official()
    assert snapshot["coverage"] == {"articles": 119, "annexes": 14, "original_recitals": 180, "amendment_recitals": 47, "complete": True}
    assert snapshot == json.loads(gzip.decompress(files("aiact").joinpath("data/full-act.json.gz").read_bytes()))
    docs = {d["id"]: d for d in snapshot["documents"]}
    assert "1a." in docs["article-6"]["text"]
    assert "2 December 2027" in docs["article-113"]["text"]
    assert "2 August 2028" in docs["article-113"]["text"]
    assert docs["article-75d"]["binding"]
    assert not docs["amendment-recital-47"]["binding"]
    assert docs["amendment-recital-47"]["source_celex"] == "32026R1744"
    assert all("▼" not in d["text"] for d in docs.values())
    assert all(d["checksum"] == checksum(d["text"].encode()) for d in docs.values())
    assert all(docs[c["document_id"]]["text"][c["start"]:c["end"]] == c["text"] for c in snapshot["chunks"])
    assert any(c["id"] == "article-6-1a" for c in snapshot["chunks"])
    assert any(c["id"] == "annex-iii-4-a" for c in snapshot["chunks"])
    assert any(c["id"] == "article-5-1-ba" for c in snapshot["chunks"])


def test_missing_provision_fails_even_with_updated_download_hash(tmp_path):
    directory = files("aiact").joinpath("data/official")
    for f in directory.iterdir():
        shutil.copy(str(f), tmp_path / f.name)
    path = tmp_path / "02024R1689-20260727.xhtml.gz"
    raw = gzip.decompress(path.read_bytes()).replace(b'id="art_75d"', b'id="removed_75d"')
    path.write_bytes(gzip.compress(raw, mtime=0))
    manifest = json.loads((tmp_path / "sources.json").read_text())
    manifest[0]["sha256"] = checksum(raw)
    (tmp_path / "sources.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="inventory"):
        import_official(tmp_path)
