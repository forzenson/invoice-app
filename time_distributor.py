import random
from schemas import InvoiceItemInput


def distribute_time(total_amount: float, items: list[InvoiceItemInput]) -> list[dict]:
    """
    Распределяет общую сумму между почасовыми позициями.
    Фиксированные позиции (is_fixed=True) сохраняют свой amount, вычитаются из total,
    остаток идёт на распределение между почасовыми позициями.

    Возвращает список словарей с полями:
        description, unit, rate, minutes, amount, is_fixed
    """
    if not items:
        return []

    # Разделяем на фиксированные и почасовые, сохраняя индексы для восстановления порядка.
    indexed = list(enumerate(items))
    fixed = [(i, it) for i, it in indexed if it.is_fixed]
    hourly = [(i, it) for i, it in indexed if not it.is_fixed]

    results = [None] * len(items)

    # Фиксированные — amount берём как есть, minutes/rate обнуляем.
    fixed_total = 0.0
    for i, it in fixed:
        amt = round(float(it.amount or 0), 2)
        fixed_total += amt
        results[i] = {
            "description": it.description,
            "unit": it.unit or "Fixed",
            "rate": 0.0,
            "minutes": 0,
            "amount": amt,
            "is_fixed": True,
        }

    # Остаток распределяем между почасовыми.
    hourly_total = round(total_amount - fixed_total, 2)
    if hourly_total < 0:
        hourly_total = 0.0

    n = len(hourly)
    if n == 0:
        return results

    if n == 1:
        i, item = hourly[0]
        rate = item.rate or 1
        minutes = round(hourly_total / rate * 60)
        minutes = max(minutes, 1)
        # amount — ровно то, что осталось, иначе Total не сходится.
        results[i] = {
            "description": item.description,
            "unit": item.unit,
            "rate": item.rate,
            "minutes": minutes,
            "amount": round(hourly_total, 2),
            "is_fixed": False,
        }
        return results

    weights = [random.uniform(0.6, 1.4) for _ in hourly]
    weight_sum = sum(weights)
    remaining = hourly_total

    for k, (i, item) in enumerate(hourly[:-1]):
        share = (weights[k] / weight_sum) * hourly_total
        rate = item.rate or 1
        minutes = round(share / rate * 60)
        minutes = max(minutes, 1)
        amount = round(minutes / 60 * rate, 2)
        remaining -= amount
        results[i] = {
            "description": item.description,
            "unit": item.unit,
            "rate": item.rate,
            "minutes": minutes,
            "amount": amount,
            "is_fixed": False,
        }

    # Последняя почасовая позиция получает остаток — сумма сходится точно.
    i_last, last = hourly[-1]
    last_amount = round(max(remaining, 0.01), 2)
    last_rate = last.rate or 1
    last_minutes = round(last_amount / last_rate * 60)
    last_minutes = max(last_minutes, 1)
    results[i_last] = {
        "description": last.description,
        "unit": last.unit,
        "rate": last.rate,
        "minutes": last_minutes,
        "amount": last_amount,
        "is_fixed": False,
    }

    return results
