"""Deterministic importer for the pinned Publications Office XHTML source pack."""
import gzip
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from importlib.resources import files
from pathlib import Path

PARSER_VERSION = "cellar-xhtml-1"
CELEX = "02024R1689-20260727"
NS = "{http://www.w3.org/1999/xhtml}"


def checksum(value) -> str:
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def text(element) -> str:
    """Normalize layout whitespace only; omit publisher revision navigation."""
    def walk(node):
        if node.get("class") in {"modref", "title-article-norm", "eli-title", "title-annex-1"}:
            return ""
        parts = [node.text or ""]
        for child in node:
            parts.extend((walk(child), child.tail or ""))
        return "".join(parts)
    return " ".join(walk(element).split())


def import_official(source_dir: Path | None = None) -> dict:
    directory = source_dir or files("aiact").joinpath("data/official")
    sources = json.loads(directory.joinpath("sources.json").read_text())
    documents = []
    for source in sources:
        raw = gzip.decompress(directory.joinpath(source["file"]).read_bytes())
        if checksum(raw) != source["sha256"]:
            raise ValueError("Official source checksum mismatch: " + source["celex"])
        root = ET.fromstring(raw)
        parents = {child: parent for parent in root.iter() for child in parent}
        prefix = r"art_[0-9]+[a-z]?|anx_[IVX]+" if source["role"] == "consolidated" else r"rct_[0-9]+"
        found = [node for node in root.iter() if re.fullmatch(prefix, node.get("id", ""))]
        for node in found:
            source_id = node.get("id")
            kind = "article" if source_id.startswith("art_") else "annex" if source_id.startswith("anx_") else "recital"
            number = source_id.split("_")[1].lower()
            document_id = ("amendment-" if source["role"] == "amendment" else "") + kind + "-" + number
            title_node = next((e for e in node.iter() if e.get("class") in {"stitle-article-norm", "title-annex-2"}), None)
            title = kind.title() + " " + number.upper()
            if title_node is not None:
                title += ": " + " ".join("".join(title_node.itertext()).split())
            body = text(node)
            if not body:
                raise ValueError("Empty official document: " + source_id)
            chapter = None
            ancestor = parents.get(node)
            while ancestor is not None:
                chapter = ancestor.get("id", "") if ancestor.get("id", "").startswith("cpt_") else chapter
                ancestor = parents.get(ancestor)
            documents.append({
                "id": document_id, "title": title, "text": body,
                "source_url": source["canonical_url"] + "#" + source_id,
                "source_celex": source["celex"], "source_anchor": source_id,
                "kind": kind, "origin": source["role"], "chapter": chapter,
                "binding": kind != "recital", "checksum": checksum(body.encode()),
                "consolidated_date": "2026-07-27" if source["role"] == "consolidated" else None,
                "publication_date": {"32024R1689": "2024-07-12", "32026R1744": "2026-07-24"}.get(source["celex"]),
                "applicability": {"status": "conditional_or_unknown", "date": None, "source_ids": ["article-111", "article-113"]},
                "blocks": [text(child) for child in node if text(child)],
            })
    actual = {d["id"] for d in documents}
    expected_articles = {"article-" + str(n) for n in range(1, 114)} | {"article-4a", "article-60a", "article-75a", "article-75b", "article-75c", "article-75d"}
    expected_annexes = {"annex-" + n for n in ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv"]}
    if {d["id"] for d in documents if d["kind"] == "article"} != expected_articles or {d["id"] for d in documents if d["kind"] == "annex"} != expected_annexes:
        raise ValueError("Consolidated article/annex inventory is incomplete or changed.")
    for source, expected in [("original", 180), ("amendment", 47)]:
        ids = {d["source_anchor"] for d in documents if d["origin"] == source}
        if ids != {"rct_" + str(i) for i in range(1, expected + 1)}:
            raise ValueError("Recital inventory is incomplete or changed: " + source)
    if len(actual) != len(documents):
        raise ValueError("Duplicate source document IDs.")
    chunks = []
    for document in documents:
        cursor, seen = 0, set()
        for index, block in enumerate(document["blocks"], 1):
            start = document["text"].find(block, cursor)
            if start < 0:
                raise ValueError("Source block cannot be mapped to parent: " + document["id"])
            cursor = start + len(block)
            match = re.match(r"^(\d+[a-z]?)\.\s", block)
            suffix = match[1] if match else "block-" + str(index)
            chunk_id = document["id"] + "-" + suffix
            if chunk_id in seen:
                chunk_id += "-" + str(index)
            seen.add(chunk_id)
            references = {"article-" + n.lower() for n in re.findall(r"Article\s+(\d+[a-z]?)", block)}
            references |= {"annex-" + n.lower() for n in re.findall(r"Annex\s+([IVX]+)\b", block)}
            chunks.append({"id": chunk_id, "document_id": document["id"], "title": document["title"] + " / " + suffix,
                           "text": block, "start": start, "end": cursor, "checksum": checksum(block.encode()),
                           "references": sorted(references & actual)})
        if not document["blocks"]:
            raise ValueError("Document has no indexable source blocks: " + document["id"])
    snapshot = {"schema_version": "1", "domain_id": "ai-act", "parser_version": PARSER_VERSION,
                "sources": sources, "documents": documents,
                "chunks": chunks,
                "coverage": {"articles": len(expected_articles), "annexes": len(expected_annexes), "original_recitals": 180, "amendment_recitals": 47, "complete": True},
                "scope_limits": ["Consolidated text is informational. Authentic legal acts are the original and amendment Official Journal publications.",
                                 "Complete pinned source inventory is distinct from retrieval quality. Conditional applicability requires context."]}
    snapshot["snapshot_id"] = checksum(snapshot)
    return snapshot


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = import_official(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(json.dumps(snapshot, ensure_ascii=False).encode(), mtime=0))
    print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "coverage": snapshot["coverage"]}))


if __name__ == "__main__":
    main()
