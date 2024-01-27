__all__ = ["percent", "percent_yield", "force_to_float_or_default"]


def percent(a, b):
    if b == 0:
        return 0
    return (a / b) * 100


def percent_yield(a, b):
    if a == 0:
        return 100
    return ((b - a) / a) * 100


def force_to_float_or_default(a, default=0.0):
    try:
        return float(a)
    except Exception:
        return default
