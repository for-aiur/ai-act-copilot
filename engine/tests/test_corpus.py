import json
import pytest
from aiact.corpus import load_corpus, update_corpus
from aiact.providers import ReviewFailure


def test_subset_and_update_preservation(tmp_path):
    data = load_corpus()
    assert len(data["sections"]) == 114
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


def test_all_expanded_passages_match_downloaded_snapshot_structure():
    from aiact.corpus import SECTION_PAGES
    data=load_corpus()
    assert len(data['source_checksums'])==15
    assert {s['id'] for s in data['sections']}==set(SECTION_PAGES)
    assert {'article-10-2','article-4a-1','annex-iv-2-b','annex-iv-2-d'} <= set(SECTION_PAGES)
    assert not any('Not present after the amendment.' in s['text'] for s in data['sections'])
    assert all(q in s['text'] for s in data['sections'] for q in s['supporting_quotes'])


def test_legacy_default_cache_uses_new_bundle_without_overwriting(tmp_path,monkeypatch):
    import aiact.corpus as corpus
    data=load_corpus()
    data['version']='reviewed-subset-2026-10-29'
    data['sections']=[s for s in data['sections'] if s['id'] in corpus.LEGACY_IDS]
    data['checksum']=corpus.digest(data['sections'])
    cache=tmp_path/'legacy.json';cache.write_text(json.dumps(data));before=cache.read_bytes()
    monkeypatch.setattr(corpus,'default_cache',lambda:cache)
    assert len(load_corpus()['sections'])==114
    assert cache.read_bytes()==before


def test_update_ignores_annotation_labels_without_ignoring_legal_changes(tmp_path):
    from aiact.corpus import Paragraphs
    data=load_corpus()
    def fetch(url):
        return ('<html>'+''.join('<p>'+s['text'].replace('. ','. </p><p>AMENDED</p><p>',1)+'</p>' for s in data['sections'] if s['url']==url)+'</html>').encode()
    result=update_corpus(tmp_path/'annotated.json',fetch=fetch)
    assert result['checksum']==data['checksum']
