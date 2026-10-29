"""Model inference is visible; decision purpose and deployment are unspecified."""


def score_records(records, trained_model):
    predictions = trained_model.predict(records)
    return predictions.tolist()
