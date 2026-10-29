"""Reproduce the reviewed subset from explicitly downloaded official HTML files.

Not a crawler or a model-generated corpus. Changes to selections require review.
"""
import hashlib
import json
from pathlib import Path
from aiact.corpus import OFFICIAL, Paragraphs, digest

selections = [
    ("annex-iii-4-a", "Annex III 4(a) · Recruitment", "annex3", "annex-3", "(a) AI systems intended to be used for the recruitment"),
    ("annex-iii-1-a", "Annex III 1(a) · Remote biometrics", "annex3", "annex-3", "(a) remote biometric identification"),
    ("article-6-2", "Article 6(2) · Annex III classification", "article6", "article-6", "2. In addition to the high-risk"),
    ("article-6-3", "Article 6(3) · Classification conditions", "article6", "article-6", "3. By derogation from paragraph 2"),
    ("article-50-1", "Article 50(1) · Direct AI interaction", "article50", "article-50", "1. Providers shall ensure"),
    ("article-50-2", "Article 50(2) · Generated content", "article50", "article-50", "2. Providers of AI systems"),
]
sections = []
source_checksums = {}
supporting_quotes = {
    "annex-iii-4-a": "AI systems intended to be used for the recruitment or selection of natural persons, in particular to place targeted job advertisements, to analyse and filter job applications, and to evaluate candidates;",
    "annex-iii-1-a": "remote biometric identification systems.",
    "article-6-2": "AI systems referred to in Annex III shall be considered to be high-risk.",
    "article-6-3": "an AI system referred to in Annex III shall not be considered to be high-risk where it does not pose a significant risk of harm to the health, safety or fundamental rights of natural persons",
    "article-50-1": "the natural persons concerned are informed that they are interacting with an AI system",
    "article-50-2": "the outputs of the AI system are marked in a machine-readable format and detectable as artificially generated or manipulated",
}
for sid, title, filename, page, prefix in selections:
    raw = Path(f"/tmp/ai-act-{filename}.html").read_bytes()
    parser = Paragraphs()
    parser.feed(raw.decode())
    matches = [text for text in parser.paragraphs if text.startswith(prefix)]
    assert len(matches) == 1, (sid, matches)
    text = matches[0]
    if sid == "annex-iii-1-a":
        text += " " + parser.paragraphs[parser.paragraphs.index(text) + 1]
    if sid == "article-6-3":
        start = parser.paragraphs.index(text)
        end = next(i for i in range(start + 1, len(parser.paragraphs)) if parser.paragraphs[i].startswith("4. A provider"))
        text = " ".join(parser.paragraphs[start:end])
    assert supporting_quotes[sid] in text
    sections.append({"id": sid, "title": title, "text": text, "supporting_quotes": [supporting_quotes[sid]], "url": OFFICIAL + page,
                     "text_kind": "binding_text_reproduced_by_commission", "applicability_date": None,
                     "checksum": hashlib.sha256(text.encode()).hexdigest()})
    source_checksums[OFFICIAL + page] = hashlib.sha256(raw).hexdigest()
data = {"version": "reviewed-subset-2026-10-29", "source_identity": "Regulation (EU) 2024/1689; Commission AI Act Service Desk reproduction, pages retrieved 2026-10-29. Articles state based on EUR-Lex consolidation as at 27 July 2026. No independent EUR-Lex version verification (endpoint blocked).",
        "retrieved_at": "2026-10-29", "verified_at": "2026-10-29", "source_checksums": source_checksums,
        "scope_limits": ["Six reviewed passages only: recruitment, remote biometric identification, Article 6 classification conditions, direct AI interaction and generated-content transparency.", "Not full AI Act coverage. No Article 5 prohibition analysis, actor-role determination, deployment facts or verified applicability dates. Consult the current official text; Commission summaries and guidance excluded.", "Refresh re-verifies reviewed passages; changed text requires manual review and a package corpus revision. It does not discover amendments."],
        "sections": sections, "checksum": digest(sections)}
destination = Path(__file__).resolve().parents[1] / "engine/src/aiact/data/corpus.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print("Verified subset:", len(sections), "passages", sum(len(s["text"]) for s in sections), "characters")
