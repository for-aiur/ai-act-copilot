"""Example only: model-assisted candidate shortlisting, not executed by the reviewer."""


def shortlist_candidates(applications, suitability_model):
    scores = suitability_model.predict([person["resume"] for person in applications])
    ranked_candidates = sorted(zip(scores, applications), key=lambda pair: pair[0], reverse=True)
    return [candidate for score, candidate in ranked_candidates[:5]]
