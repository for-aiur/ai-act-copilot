"""Example: a customer-facing support chatbot that returns generated text."""


def reply_to_customer(customer_message, language_model):
    generated_reply = language_model.generate(customer_message)
    return {"speaker": "Support", "message": generated_reply}
