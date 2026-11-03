"""Reproducible generic retrieval metrics and explicit quality policy."""
import math
from statistics import mean

from .contracts import GoldenCase, RetrievalResult


def score_case(case: GoldenCase, result: RetrievalResult, k=10):
    if case.request.domain_id != result.request.domain_id or case.snapshot_id != result.snapshot_id:
        raise ValueError("Golden case and retrieval run use different domain/source snapshots")
    if case.request.fingerprint() != result.context_fingerprint:
        raise ValueError("Golden case and retrieval run use different scenario contexts")
    hits = list(dict.fromkeys(c.document.id for c in result.candidates))[:k]
    required = {label.document_id for label in case.labels if label.label == "must_retrieve"}
    relevant = {label.document_id for label in case.labels if label.label in {"must_retrieve", "relevant"}}
    negative = {label.document_id for label in case.labels if label.label == "not_relevant"}
    found = required & set(hits)
    ranks = [index + 1 for index, identity in enumerate(hits) if identity in relevant]
    dcg = sum(1 / math.log2(rank + 1) for rank in ranks)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(relevant)) + 1))
    return {
        "case_id": case.id, "revision": case.revision, "status": case.status,
        "split": case.split, "context_fingerprint": result.context_fingerprint,
        "snapshot_id": result.snapshot_id, "rag_release_id": result.rag_release_id,
        "k": k, "hits": hits, "missed_required": sorted(required - set(hits)),
        "false_positives": sorted(negative & set(hits)), "required_count": len(required), "required_found": len(found),
        "recall": len(found) / len(required) if required else None,
        "precision": len(relevant & set(hits)) / len(hits) if hits else 0,
        "mrr": 1 / ranks[0] if ranks else 0, "ndcg": dcg / ideal if ideal else None,
        "elapsed_ms": result.elapsed_ms,
    }


def wilson(successes, total):
    if not total:
        return None
    z = 1.96
    p = successes / total
    denominator = 1 + z * z / total
    middle = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0, middle - half), min(1, middle + half)]


def summarize(scores):
    total = sum(s["required_count"] for s in scores)
    found = sum(s["required_found"] for s in scores)
    return {"cases": len(scores), "required_labels": total, "required_found": found,
        "recall": found / total if total else None, "recall_wilson_95": wilson(found, total),
        "mean_precision": mean(s["precision"] for s in scores) if scores else None,
        "mean_mrr": mean(s["mrr"] for s in scores) if scores else None,
        "false_positives": sum(len(s["false_positives"]) for s in scores),
        "missing_required": sum(len(s["missed_required"]) for s in scores),
        "uncertainty_note": "Label-level Wilson interval; related labels and small scenario samples limit generalization."}


def quality_gate(cases: list[GoldenCase], scores: list[dict]):
    approved = [c for c in cases if c.status == "approved"]
    approved_scores = [s for s in scores if any(c.id == s["case_id"] and c.revision == s["revision"] for c in approved)]
    holdout = [s for s in approved_scores if s["split"] == "holdout"]
    critical = [s for s in approved_scores if s["split"] == "critical"]
    summary = summarize(holdout)
    areas = {c.area for c in approved if c.area != "unspecified"}
    reasons = []
    if len(approved) < 50:
        reasons.append("At least 50 explicitly approved cases are required.")
    if len(areas) < 10:
        reasons.append("At least 10 distinct source areas are required.")
    if not holdout or summary["recall"] is None or summary["recall"] < .95:
        reasons.append("Approved untouched holdout Recall@10 must reach 0.95.")
    if any(c.split == "holdout" and not c.holdout_sealed for c in approved):
        reasons.append("Holdout must be explicitly sealed before tuning.")
    if not critical or any(s["missed_required"] for s in critical):
        reasons.append("A separate approved critical suite must have zero mandatory misses.")
    if len(approved_scores) != len(approved):
        reasons.append("Every approved case must have a version-matched evaluation.")
    return {"status": "pass" if not reasons else "blocked", "reasons": reasons, "holdout": summary,
            "policy_version": "m1-1", "targets_are_claims": False}
