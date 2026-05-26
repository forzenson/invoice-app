import random
from schemas import InvoiceItemInput


def distribute_time(total_amount: float, items: list[InvoiceItemInput]) -> list[dict]:
    """
    Случайно распределяет общую сумму между позициями.
    Для каждой позиции рассчитывает время в минутах исходя из ставки.

    Возвращает список словарей с полями:
        description, unit, rate, minutes, amount
    """
    n = len(items)
    if n == 0:
        return []

    if n == 1:
        item = items[0]
        minutes = round(total_amount / item.rate * 60)
        minutes = max(minutes, 1)
        amount = round(minutes / 60 * item.rate, 2)
        return [{
            "description": item.description,
            "unit": item.unit,
            "rate": item.rate,
            "minutes": minutes,
            "amount": amount,
        }]

    # Случайные веса — чуть отклоняем от равномерного, но не слишком
    weights = [random.uniform(0.6, 1.4) for _ in items]
    weight_sum = sum(weights)

    result = []
    remaining = total_amount

    for i, item in enumerate(items[:-1]):
        share = (weights[i] / weight_sum) * total_amount
        minutes = round(share / item.rate * 60)
        minutes = max(minutes, 1)
        amount = round(minutes / 60 * item.rate, 2)
        remaining -= amount
        result.append({
            "description": item.description,
            "unit": item.unit,
            "rate": item.rate,
            "minutes": minutes,
            "amount": amount,
        })

    # Последняя позиция получает остаток — сумма сходится точно
    last = items[-1]
    last_amount = round(max(remaining, 0.01), 2)
    last_minutes = round(last_amount / last.rate * 60)
    last_minutes = max(last_minutes, 1)

    result.append({
        "description": last.description,
        "unit": last.unit,
        "rate": last.rate,
        "minutes": last_minutes,
        "amount": last_amount,
    })

    return result
