import json
import pytest
from aiact.corpus import load_corpus, update_corpus
from aiact.providers import ReviewFailure


def test_subset_and_update_preservation(tmp_path):
    data = load_corpus()
    assert len(data["sections"]) == 6
    target = tmp_path / "corpus.json"
    target.write_text(json.dumps(data))
    original = target.read_bytes()
    with pytest.raises(ReviewFailure, match="changed or is missing"):
        update_corpus(target, fetch=lambda url: b"<p>invalid download</p>")
    assert target.read_bytes() == original
    def fetch(url):
        return ("<html>" + "".join("<p>" + s["text"] + "</p>" for s in data["sections"] if s["url"] == url) + "</html>").encode()
    update_corpus(target, fetch=fetch)
    assert load_corpus(target)["checksum"] == data["checksum"]


def test_corrupt_missing_cache(tmp_path):
    with pytest.raises(ReviewFailure, match="absent"):
        load_corpus(tmp_path / "missing")
    data = load_corpus()
    data["sections"][0]["text"] = "invented"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ReviewFailure, match="integrity"):
        load_corpus(path)
