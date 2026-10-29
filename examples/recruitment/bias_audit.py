"""Synthetic special-category data audit scenario. No real personal records.

The example illustrates questions about the exceptional bias-audit purpose,
necessity, restricted access and deletion. It establishes no legal permission.
"""


def audit_recruitment_bias(candidate_rows, suitability_model):
    scores = suitability_model.predict([row["skills_score"] for row in candidate_rows])
    sensitive_bias_audit_records = [
        {"ethnicity": row["ethnicity"], "score": score}
        for row, score in zip(candidate_rows, scores)
    ]
    # Return temporary audit records; retention/deletion and access controls
    # are not established here and must be checked in the wider system.
    return sensitive_bias_audit_records
