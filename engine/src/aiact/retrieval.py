"""Small deterministic lexical ranker, with explicit demo-domain synonyms."""
import re
from .context import Budgets

DOMAINS = {
    "annex-iii-4-a": {"recruitment", "recruit", "resume", "candidate", "applicant", "hiring", "job", "cv", "employment", "shortlist"},
    "annex-iii-1-a": {"biometric", "biometrics", "face", "facial", "identify", "identification", "watchlist", "camera", "gallery"},
    "article-50-1": {"chatbot", "chat", "assistant", "conversation", "interact", "customer", "reply"},
    "article-50-2": {"synthetic", "deepfake", "watermark", "generative"},
}


def retrieve(query: str, corpus: dict, budgets: Budgets = Budgets()) -> list[dict]:
    tokens = set(re.findall(r"[a-z]+", query.lower().replace("_", " ")))
    def score(section):
        words = set(re.findall(r"[a-z]+", section["text"].lower()))
        return 10 * len(tokens & DOMAINS.get(section["id"], set())) + len(tokens & words)
    ranked = sorted(corpus["sections"], key=lambda s: (-score(s), s["id"]))
    # Keep unrelated domains out of a small model's legal context. With no domain
    # signal, retain general classification conditions; never discard source.
    domains = {sid for sid, words in DOMAINS.items() if tokens & words}
    # The first review asks about deployment context, not legal classification.
    # A focused domain passage is sufficient; retain general conditions when
    # the domain itself is unknown. This also bounds CPU prompt latency.
    wanted = domains or {"article-6-2", "article-6-3"}
    ranked = [s for s in ranked if s["id"] in wanted]
    selected, used = [], 0
    for section in ranked:
        size = len(section["text"].encode())
        if len(selected) < budgets.passages and used + size <= budgets.legal_bytes:
            selected.append(section)
            used += size
    return selected
