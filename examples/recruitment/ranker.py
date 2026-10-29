"""Example only: model-assisted candidate shortlisting, not executed by the reviewer."""


def shortlist_candidates(applications, suitability_model):
    scores = suitability_model.predict([person["resume"] for person in applications])
    ranked_candidates = sorted(zip(scores, applications), key=lambda pair: pair[0], reverse=True)
    return [candidate for score, candidate in ranked_candidates[:5]]


def automatically_reject_candidates(applications, suitability_model, cutoff=0.6):
    """Synthetic demo: reject applicants below a model-score cutoff."""
    scores = suitability_model.predict([person["resume"] for person in applications])
    return [
        {"candidate_id": person["id"], "decision": "rejected", "score": float(score)}
        for person, score in zip(applications, scores)
        if score < cutoff
    ]
