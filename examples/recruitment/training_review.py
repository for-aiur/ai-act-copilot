"""Synthetic hiring workflow for review. Never run by the scanner.

Intentionally leaves dataset provenance, label checks, independent validation
and the recruiter's override process outside this snippet. These are unknowns,
not proof that safeguards are absent from the wider system.
"""


def train_candidate_model(training_rows, model_factory):
    hyperparameters = {"max_depth": 8, "class_weight": "balanced", "random_state": 42}
    dataset = [row for row in training_rows if row["experience_years"] is not None]
    features = [[row["experience_years"], row["skills_score"]] for row in dataset]
    labels = [row["historically_hired"] for row in dataset]
    suitability_model = model_factory(**hyperparameters)
    suitability_model.fit(features, labels)
    return suitability_model


def shortlist_candidates(applications, suitability_model, threshold=0.75):
    features = [[row["experience_years"], row["skills_score"]] for row in applications]
    scores = suitability_model.predict_proba(features)
    ranked_candidates = sorted(zip(scores, applications), key=lambda pair: pair[0][1], reverse=True)
    return [candidate for score, candidate in ranked_candidates if score[1] >= threshold][:5]


def retrain_from_hiring_history(decision_rows, model_factory):
    """Synthetic demo: learn from applicants selected by an earlier model."""
    training_rows = [row for row in decision_rows if row["previously_shortlisted"]]
    features = [
        [row["experience_years"], row["skills_score"], row["employment_gap_months"]]
        for row in training_rows
    ]
    labels = [int(row["historically_hired"]) for row in training_rows]
    suitability_model = model_factory(max_depth=12, class_weight="balanced")
    suitability_model.fit(features, labels)
    return suitability_model
