__all__ = ["percent", "percent_yield"]


def percent(a, b):
    if b == 0:
        return 0
    return (a / b) * 100


def percent_yield(a, b):
    if a == 0:
        return 100
    return ((b - a) / a) * 100
