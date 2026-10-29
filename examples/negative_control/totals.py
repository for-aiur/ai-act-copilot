"""Ordinary arithmetic; no AI system or model inference."""


def invoice_total(prices, tax_rate):
    subtotal = sum(prices)
    return round(subtotal * (1 + tax_rate), 2)
